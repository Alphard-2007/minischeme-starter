"""mini-Scheme 运行时的「值」（数据类型）定义。

设计要点（对应 spec §6、§8、§11）：

- 列表统一用「点对链」表示：``(1 2 3)`` 就是
  ``Pair(1, Pair(2, Pair(3, EMPTY)))``。解析阶段就把 ``'(1 2 3)`` 这样的
  字面量造成点对链，所以 quote 出来的数据与 cons 出来的数据是同一种表示，
  不会出现 spec §11 提到的 ``(1 2 . 3)`` 打印错误。
- 符号 ``Symbol`` 是独立的类，**不是** ``str`` 的子类，避免 ``equal?`` 把
  符号 ``'a`` 和字符串 ``"a"`` 判成相等。
- 布尔直接用 Python 的 ``True``/``False``。因为 Python 里 ``True == 1``，
  所有比较都必须先用 ``isinstance(x, bool)`` 把布尔摘出来单独处理。
- 「无值」用 Python 的 ``None`` 表示。Scheme 的值域里没有 None，
  因此它可以安全地当作「这个表达式不打印」的标记（spec §2）。
- 空表 ``EMPTY`` 是**单例**，于是 ``(eq? '() '())`` 天然为真；
  而每次解析 ``'(1)`` 都会新建 Pair 对象，于是 ``(eq? '(1) '(1))`` 为假，
  正好符合 spec §5 对 ``eq?`` 的要求（复合数据比同一性）。
"""

from __future__ import annotations

import re

from errors import SchemeArityError, SchemeSyntaxError, SchemeTypeError

__all__ = [
    "EMPTY",
    "Builtin",
    "Closure",
    "Pair",
    "Symbol",
    "is_truthy",
    "pair_to_list",
    "proper_list",
    "scheme_equal",
    "scheme_eq",
    "symbol",
]


# ---------------------------------------------------------------------------
# 符号
# ---------------------------------------------------------------------------

class Symbol:
    """符号（名字）。刻意不继承 str，以便和字符串区分开。"""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:  # 便于调试；正式打印走 printer 模块
        return self.name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Symbol) and other.name == self.name

    def __hash__(self) -> int:
        return hash(("symbol", self.name))


# 符号驻留表：同名符号复用同一个对象，省内存也让 `is` 比较成立。
_INTERNED: dict[str, Symbol] = {}


def symbol(name: str) -> Symbol:
    """取得（必要时创建）名为 ``name`` 的符号。"""
    sym = _INTERNED.get(name)
    if sym is None:
        sym = Symbol(name)
        _INTERNED[name] = sym
    return sym


# ---------------------------------------------------------------------------
# 空表与点对
# ---------------------------------------------------------------------------

class _Empty:
    """空表 ``()``。全局只有一个实例。"""

    __slots__ = ()

    def __repr__(self) -> str:
        return "()"


EMPTY = _Empty()


class Pair:
    """点对：``car`` 是第一个元素，``cdr`` 是「剩下的链」。

    不定义 ``__eq__``，保留 Python 默认的「同一性」比较——
    这正是 ``eq?`` 对复合数据所需要的语义。
    """

    __slots__ = ("car", "cdr")

    def __init__(self, car: object, cdr: object) -> None:
        self.car = car
        self.cdr = cdr

    def __repr__(self) -> str:  # 调试用，不用于评分输出
        return f"Pair({self.car!r}, {self.cdr!r})"


def build_list(items, tail=EMPTY):
    """把 Python 可迭代对象 ``items`` 造成点对链，链尾接在 ``tail`` 上。"""
    result = tail
    for item in reversed(list(items)):
        result = Pair(item, result)
    return result


def pair_to_list(chain, context: str = "表达式"):
    """把「真列表」的点对链转成 Python 列表。

    链尾若不是空表（即写成了点对 ``(a b . c)``）就报语法错误，
    这样特殊形式的参数列表能被严格校验。
    """
    items = []
    current = chain
    while current is not EMPTY:
        if not isinstance(current, Pair):
            raise SchemeSyntaxError(f"{context}：参数写法不正确（期望一个列表）")
        items.append(current.car)
        current = current.cdr
    return items


def proper_list(value) -> bool:
    """判断 ``value`` 是否为「真列表」（沿 cdr 走到底一定是空表）。

    用「已访问节点」集合做环检测：数据里若意外出现环，返回 False 而不是死循环。
    兄弟结构可以重复访问，这里只沿 cdr 一条链向下走，不影响 ``append``
    之类共享子结构的正常数据。
    """
    seen = set()
    current = value
    while True:
        if current is EMPTY:
            return True
        if not isinstance(current, Pair):
            return False  # 链尾是别的东西 → 点对，不是真列表
        if id(current) in seen:
            return False  # 出现环
        seen.add(id(current))
        current = current.cdr


# ---------------------------------------------------------------------------
# 过程：内置过程与用户闭包
# ---------------------------------------------------------------------------

class Builtin:
    """内置过程：包一个 Python 函数，外加参数个数检查。

    ``min_args``/``max_args`` 为 None 表示不限（``max_args=None`` 即可变参数）。
    """

    __slots__ = ("name", "fn", "min_args", "max_args")

    def __init__(self, name: str, fn, min_args: int = 0, max_args=None) -> None:
        self.name = name
        self.fn = fn
        self.min_args = min_args
        self.max_args = max_args

    def check_arity(self, args) -> None:
        count = len(args)
        if count < self.min_args or (self.max_args is not None and count > self.max_args):
            raise SchemeArityError(
                f"{self.name}：参数个数不对（收到 {count} 个，"
                f"要求 {_arity_text(self.min_args, self.max_args)}）"
            )

    def __repr__(self) -> str:
        return "#<procedure>"


class Closure:
    """用户定义的函数（闭包）：记住**定义时**的环境，这是词法作用域的关键。

    ``params`` 是 Python 的符号列表（固定个数，本语言不支持可变参数 lambda），
    ``body`` 是已经转成 Python 列表的函数体表达式。
    """

    __slots__ = ("params", "body", "env", "name")

    def __init__(self, params, body, env, name=None) -> None:
        self.params = params
        self.body = body
        self.env = env
        self.name = name

    def check_arity(self, args) -> None:
        if len(args) != len(self.params):
            raise SchemeArityError(
                f"{self.name or '匿名函数'}：需要 {len(self.params)} 个参数，"
                f"实际收到 {len(args)} 个"
            )

    def __repr__(self) -> str:
        return "#<procedure>"


def is_procedure(value) -> bool:
    """是否为过程（内置过程或闭包）。"""
    return isinstance(value, (Builtin, Closure))


def _arity_text(min_args: int, max_args) -> str:
    if max_args is None:
        return f"至少 {min_args} 个" if min_args else "任意个"
    if min_args == max_args:
        return f"{min_args} 个"
    return f"{min_args} 到 {max_args} 个"


# ---------------------------------------------------------------------------
# 真值判断与相等关系
# ---------------------------------------------------------------------------

def is_truthy(value) -> bool:
    """Scheme 的真值规则：**只有 ``#f`` 是假**，``0``、``()``、``""`` 都是真。"""
    return value is not False


def _is_number(value) -> bool:
    """是数字（bool 虽然是 int 的子类，但不算数字）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def scheme_eq(left, right) -> bool:
    """``eq?``：符号/数字/布尔按值比较，复合数据比同一性（spec §5）。"""
    # 布尔先摘出来：Python 里 True == 1，不先判断就会把 #t 和 1 判成相等。
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, Symbol) or isinstance(right, Symbol):
        return isinstance(left, Symbol) and isinstance(right, Symbol) and left.name == right.name
    if _is_number(left) and _is_number(right):
        # 整数与浮点视为不同（(eq? 1 1.0) 为假），同类型才比值。
        return type(left) is type(right) and left == right
    return left is right


def scheme_equal(left, right) -> bool:
    """``equal?``：逐层比较结构；先比类型再比值（spec §11 的两个陷阱都在这里避开）。"""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if isinstance(left, Symbol) or isinstance(right, Symbol):
        return isinstance(left, Symbol) and isinstance(right, Symbol) and left.name == right.name
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    if isinstance(left, Pair) and isinstance(right, Pair):
        return scheme_equal(left.car, right.car) and scheme_equal(left.cdr, right.cdr)
    if isinstance(left, Pair) or isinstance(right, Pair):
        return False  # 一个是点对、另一个不是
    if _is_number(left) and _is_number(right):
        return left == right  # equal? 按数值比较：1 与 1.0 相等
    return left is right


# ---------------------------------------------------------------------------
# 类型检查小工具（内置过程共用）
# ---------------------------------------------------------------------------

def require_number(value, who: str):
    if not _is_number(value):
        raise SchemeTypeError(f"{who}：参数必须是数字，收到 {_describe(value)}")
    return value


def require_pair(value, who: str) -> Pair:
    if not isinstance(value, Pair):
        raise SchemeTypeError(f"{who}：参数必须是非空列表（点对），收到 {_describe(value)}")
    return value


def require_proper_list(value, who: str):
    if not proper_list(value):
        raise SchemeTypeError(f"{who}：参数必须是真列表，收到 {_describe(value)}")
    return value


def _describe(value) -> str:
    """错误信息里对值的简短描述（避免与 printer 模块循环依赖）。"""
    if value is None:
        return "无值"
    if value is EMPTY:
        return "()"
    if isinstance(value, bool):
        return "#t" if value else "#f"
    if isinstance(value, Symbol):
        return f"符号 {value.name}"
    if isinstance(value, str):
        return "字符串"
    if isinstance(value, Pair):
        return "点对"
    if isinstance(value, (Builtin, Closure)):
        return "过程"
    return repr(value)


# 供 parser 使用的数字字面量识别（放在这里，避免 lexer/parser 各写一份）
_INT_RE = re.compile(r"^[+-]?[0-9]+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?$")


def parse_number_literal(text: str):
    """把词法阶段的 atom 文本试着解析成数字；不是数字就返回 None。

    刻意不用 ``int()``/``float()`` 直接试：那样 ``inf``、``nan`` 这类
    本应是符号的写法也会被当成数字。
    """
    if _INT_RE.match(text):
        return int(text)
    if _FLOAT_RE.match(text):
        return float(text)
    return None
