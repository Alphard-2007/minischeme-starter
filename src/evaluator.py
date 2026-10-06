"""求值器：表达式 → 值（README §4 说的「心脏」）。

核心是两个互相递归的函数：

- ``evaluate(expr, env)``：符号查环境；自求值数据原样返回；点对链则先看
  头部是不是特殊形式（quote/if/cond/and/or/define/lambda/let/begin），
  是就按 spec §4 各自的求值顺序处理，否则是函数调用——先求值操作符和
  全部实参，再交给 ``apply_procedure``。
- ``apply_procedure(proc, args)``：内置过程直接调 Python 函数；闭包则新建
  一层子环境（外层指向**定义时**的环境）把实参绑到参数名上，再回到
  ``evaluate`` 求值函数体。

两个函数互相调用构成循环，这就是解释器能跑起来的原因。
"""

from __future__ import annotations

from environment import Environment
from errors import SchemeArityError, SchemeSyntaxError, SchemeTypeError
from values import (
    EMPTY,
    Builtin,
    Closure,
    Pair,
    Symbol,
    build_list,
    is_truthy,
    pair_to_list,
    symbol,
)

__all__ = ["apply_procedure", "eval_body", "evaluate"]

# 特殊形式的名字 → 处理函数。用字典做分派，比一长串 if 更清楚也更好扩展。
_SPECIAL_FORMS = {}


def _special_form(name: str):
    """注册一个特殊形式的装饰器。"""

    def register(handler):
        _SPECIAL_FORMS[symbol(name)] = handler
        return handler

    return register


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def evaluate(expr, env: Environment):
    """求值一个表达式，返回它的值（``None`` 表示「无值」，不打印）。"""
    # 括号表达式（点对链）：特殊形式或函数调用
    if isinstance(expr, Pair):
        return _eval_pair(expr, env)

    # 符号：去环境里查（沿作用域链向外）
    if isinstance(expr, Symbol):
        return env.lookup(expr)

    # 自求值数据：数字、布尔、字符串、空表
    if expr is None or isinstance(expr, (int, float, str, bool)) or expr is EMPTY:
        if expr is None:
            raise SchemeSyntaxError("表达式缺失：这里应该有一个值")
        return expr

    raise SchemeSyntaxError(f"无法求值的表达式：{expr!r}")


def _eval_pair(expr: Pair, env: Environment):
    head = expr.car

    # 特殊形式：头部是关键字符号（且该符号确实被当作关键字使用）
    if isinstance(head, Symbol) and head in _SPECIAL_FORMS:
        return _SPECIAL_FORMS[head](expr.cdr, env)

    # 普通函数调用：先求值操作符，再从左到右求值全部实参（应用序，spec §9）
    procedure = evaluate(head, env)
    args = [evaluate(item, env) for item in pair_to_list(expr.cdr, "函数调用")]
    return apply_procedure(procedure, args)


def apply_procedure(procedure, args: list):
    """调用一个过程。``args`` 是已经求值完毕的实参列表。"""
    if isinstance(procedure, Builtin):
        procedure.check_arity(args)
        return procedure.fn(args)

    if isinstance(procedure, Closure):
        procedure.check_arity(args)
        # 新建一层环境：外层指向闭包**定义时**的环境（词法作用域）
        frame = procedure.env.child(procedure.name or "匿名函数")
        for param, value in zip(procedure.params, args):
            frame.define(param, value)
        return eval_body(procedure.body, frame)

    raise SchemeTypeError(
        f"不能把 {_brief(procedure)} 当函数调用（它不是过程）"
    )


def eval_body(body, env: Environment):
    """按 ``begin`` 语义依次求值一组表达式，返回最后一个的结果；空则返回 None。"""
    result = None
    for expr in body:
        result = evaluate(expr, env)
    return result


# ---------------------------------------------------------------------------
# 特殊形式实现（每个都注明了 spec §4 里对应的求值顺序）
# ---------------------------------------------------------------------------

@_special_form("quote")
def _eval_quote(args: Pair, env: Environment):
    """§4.1：原样返回数据，**不求值**。"""
    items = pair_to_list(args, "quote")
    if len(items) != 1:
        raise SchemeSyntaxError(f"quote：只能引用一个数据，收到 {len(items)} 个")
    return items[0]


@_special_form("if")
def _eval_if(args: Pair, env: Environment):
    """§4.2：先求值测试，只走一个分支（另一个分支根本不执行）。"""
    items = pair_to_list(args, "if")
    if len(items) not in (2, 3):
        raise SchemeSyntaxError(f"if：需要 2 或 3 个部分，收到 {len(items)} 个")
    test = evaluate(items[0], env)
    if is_truthy(test):
        return evaluate(items[1], env)
    if len(items) == 3:
        return evaluate(items[2], env)
    return None  # 省略假分支且测试为 #f → 无值，不打印


@_special_form("cond")
def _eval_cond(args: Pair, env: Environment):
    """§4.3：从上到下求值每个测试，命中后按 begin 语义求值它的表达式。"""
    clauses = pair_to_list(args, "cond")
    for clause in clauses:
        parts = pair_to_list(clause, "cond 子句")
        if not parts:
            raise SchemeSyntaxError("cond：子句不能是空括号 ()")
        test_expr = parts[0]
        if isinstance(test_expr, Symbol) and test_expr.name == "else":
            # else 是兜底子句，不再求值它本身
            return eval_body(parts[1:], env) if len(parts) > 1 else None
        test = evaluate(test_expr, env)
        if is_truthy(test):
            if len(parts) == 1:
                return test  # 子句里没有表达式 → 返回测试值本身
            return eval_body(parts[1:], env)
    return None  # 全部不匹配


@_special_form("and")
def _eval_and(args: Pair, env: Environment):
    """§4.4：从左到右，遇到第一个 #f 立刻返回（短路），否则返回最后一个值。"""
    items = pair_to_list(args, "and")
    result = True  # (and) → #t
    for item in items:
        result = evaluate(item, env)
        if not is_truthy(result):
            return result  # 短路：后面的表达式不执行
    return result


@_special_form("or")
def _eval_or(args: Pair, env: Environment):
    """§4.4：从左到右，遇到第一个不为 #f 的值立刻返回（短路）。"""
    items = pair_to_list(args, "or")
    for item in items:
        result = evaluate(item, env)
        if is_truthy(result):
            return result  # 短路：后面的表达式不执行
    return False  # (or) 或全为 #f → #f


@_special_form("define")
def _eval_define(args: Pair, env: Environment):
    """§4.5：先求值右侧表达式，再在**当前**环境绑定；结果是符号名本身。

    支持两种写法：
    - ``(define 名 表达式)``
    - ``(define (函数名 参数...) 体...)``  —— lambda 的简写
    """
    if args is EMPTY or not isinstance(args, Pair):
        raise SchemeSyntaxError("define：写法不正确")

    target = args.car

    # 函数定义简写
    if isinstance(target, Pair):
        signature = pair_to_list(target, "define 的函数签名")
        if not signature or not isinstance(signature[0], Symbol):
            raise SchemeSyntaxError("define：函数名必须是符号")
        name = signature[0]
        params = _parse_params(build_list(signature[1:]), "define")
        body = pair_to_list(args.cdr, "define 的函数体")
        closure = Closure(params, body, env, name.name)
        env.define(name, closure)
        return name

    if not isinstance(target, Symbol):
        raise SchemeSyntaxError("define：第一个部分必须是名字（符号）或函数签名")

    values = pair_to_list(args.cdr, "define")
    if len(values) != 1:
        raise SchemeSyntaxError(f"define：只能有一个值表达式，收到 {len(values)} 个")
    env.define(target, evaluate(values[0], env))
    return target


@_special_form("lambda")
def _eval_lambda(args: Pair, env: Environment):
    """§4.6：函数体此时**不求值**；产生一个记住当前环境的闭包。"""
    items = pair_to_list(args, "lambda")
    if len(items) < 1:
        raise SchemeSyntaxError("lambda：缺少参数列表")
    params = _parse_params(items[0], "lambda")
    return Closure(params, items[1:], env)


@_special_form("let")
def _eval_let(args: Pair, env: Environment):
    """§4.7：**并行**绑定——每个绑定表达式都在**外层**环境求值完，
    再在新环境里按 begin 语义求值函数体（所以绑定之间互不可见）。
    """
    items = pair_to_list(args, "let")
    if len(items) < 1:
        raise SchemeSyntaxError("let：缺少绑定列表")

    bindings_raw = pair_to_list(items[0], "let 的绑定列表")
    pairs = []
    for binding in bindings_raw:
        parts = pair_to_list(binding, "let 的单个绑定")
        if len(parts) != 2 or not isinstance(parts[0], Symbol):
            raise SchemeSyntaxError("let：每个绑定必须写成 (名字 表达式)")
        # 关键：在外层环境求值，这样后面的绑定看不见前面的绑定
        pairs.append((parts[0], evaluate(parts[1], env)))

    frame = env.child("let")
    for name, value in pairs:
        frame.define(name, value)
    return eval_body(items[1:], frame)


@_special_form("begin")
def _eval_begin(args: Pair, env: Environment):
    """§4.8：从左到右依次求值，返回最后一个的结果。"""
    return eval_body(pair_to_list(args, "begin"), env)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _parse_params(params_expr, who: str) -> list:
    """校验并返回参数符号列表（本语言只支持固定个数参数，spec §10）。"""
    params = pair_to_list(params_expr, f"{who} 的参数列表")
    seen = set()
    for param in params:
        if not isinstance(param, Symbol):
            raise SchemeSyntaxError(f"{who}：参数名必须是符号")
        if param.name in seen:
            raise SchemeSyntaxError(f"{who}：参数名重复：{param.name}")
        seen.add(param.name)
    return params


def _brief(value) -> str:
    """错误信息里对值的简短描述（不依赖 printer，避免循环导入）。"""
    if isinstance(value, bool):
        return "#t" if value else "#f"
    if isinstance(value, Symbol):
        return f"符号 {value.name}"
    if isinstance(value, str):
        return "字符串"
    if value is EMPTY:
        return "()"
    if isinstance(value, Pair):
        return "列表"
    if value is None:
        return "无值"
    return repr(value)


# 让静态检查知道这些导入确实被用到
_ = (SchemeArityError,)
