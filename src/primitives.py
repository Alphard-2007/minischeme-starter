"""内置库：spec §5 的全部内置过程，放进初始全局环境。

约定：每个内置过程都是一个 ``Builtin``，参数**已经在求值器里全部求值完毕**
（这正是「特殊形式」和「内置过程」的区别）。参数个数检查由 ``Builtin``
统一完成，这里只关心语义。

几个容易踩的坑（spec §5 / §11）都做了专门处理：
- ``/`` 与 ``quotient``：整数相除要得到**向零截断**的整数商，
  所以不能直接用 Python 的 ``//``（它是向下取整，``-7 // 2 == -4``）。
- ``modulo``：结果符号跟除数，正好等价于 Python 的 ``%``。
- 布尔值是 ``int`` 的子类，所以判断「是数字」时必须先把 ``bool`` 排除。
"""

from __future__ import annotations

import sys

from environment import Environment
from errors import SchemeArityError, SchemeTypeError, SchemeValueError
from printer import to_display_string
from values import (
    EMPTY,
    Builtin,
    Pair,
    Symbol,
    build_list,
    is_number,
    is_procedure,
    is_truthy,
    pair_to_list,
    proper_list,
    require_number,
    require_pair,
    require_proper_list,
    scheme_eq,
    scheme_equal,
    symbol,
)

__all__ = ["make_global_env"]


# ---------------------------------------------------------------------------
# 算术
# ---------------------------------------------------------------------------

def _numbers(args, who: str):
    """把参数全部校验成数字。"""
    for arg in args:
        require_number(arg, who)
    return args


def _truncate_divide(left, right):
    """一次除法：整数相除得向零截断的整数商，否则做浮点除法。"""
    if right == 0:
        raise SchemeValueError("/：除数不能为 0")
    if isinstance(left, int) and isinstance(right, int):
        quotient = abs(left) // abs(right)
        # 两数异号时商为负（向零截断）
        return -quotient if (left < 0) != (right < 0) else quotient
    return left / right


def _builtin_add(args):
    _numbers(args, "+")
    total = 0
    for arg in args:
        total += arg
    return total


def _builtin_sub(args):
    _numbers(args, "-")
    if not args:
        raise SchemeArityError("-：至少需要 1 个参数")
    if len(args) == 1:
        return -args[0]  # 单参数取反：(- 5) → -5
    total = args[0]
    for arg in args[1:]:
        total -= arg
    return total


def _builtin_mul(args):
    _numbers(args, "*")
    total = 1
    for arg in args:
        total *= arg
    return total


def _builtin_div(args):
    _numbers(args, "/")
    if not args:
        raise SchemeArityError("/：至少需要 1 个参数")
    if len(args) == 1:
        if args[0] == 0:
            raise SchemeValueError("/：除数不能为 0")
        return 1 / args[0]  # 单参数求倒数，结果一定是浮点（spec §5）
    result = args[0]
    for arg in args[1:]:
        result = _truncate_divide(result, arg)
    return result


def _builtin_modulo(args):
    left, right = args
    for value in args:
        if not isinstance(value, int) or isinstance(value, bool):
            raise SchemeTypeError("modulo：参数必须是整数")
    if right == 0:
        raise SchemeValueError("modulo：除数不能为 0")
    return left % right  # Python 的 % 结果符号跟除数，正是 Scheme modulo 的语义


def _builtin_quotient(args):
    left, right = args
    for value in args:
        if not isinstance(value, int) or isinstance(value, bool):
            raise SchemeTypeError("quotient：参数必须是整数")
    if right == 0:
        raise SchemeValueError("quotient：除数不能为 0")
    quotient = abs(left) // abs(right)
    return -quotient if (left < 0) != (right < 0) else quotient


def _builtin_expt(args):
    base, exponent = args
    _numbers(args, "expt")
    if base == 0 and exponent < 0:
        raise SchemeValueError("expt：0 不能取负数次幂")
    return base ** exponent


def _builtin_abs(args):
    (value,) = args
    require_number(value, "abs")
    return abs(value)


# ---------------------------------------------------------------------------
# 比较
# ---------------------------------------------------------------------------

def _compare_order(left, right, who: str):
    """给两个「同类可排序」的值排序：小于返回 -1，相等返回 0，大于返回 1。

    支持数字、符号（按名字字典序）与字符串（按字典序）；
    不同类型之间无法排序，报错。
    """
    if is_number(left) and is_number(right):
        return -1 if left < right else (0 if left == right else 1)
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return -1 if left.name < right.name else (0 if left.name == right.name else 1)
    if isinstance(left, str) and isinstance(right, str):
        return -1 if left < right else (0 if left == right else 1)
    raise SchemeTypeError(f"{who}：这两个值无法比较大小（类型不同或不是可排序类型）")


def _same_for_equals(left, right) -> bool:
    """``=`` 的相邻两项比较：数字比值、符号比名字、字符串比内容，其余为假。"""
    if is_number(left) and is_number(right):
        return left == right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left.name == right.name
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    if isinstance(left, bool) and isinstance(right, bool):
        return left is right
    return False


def _make_ordering(who: str, predicate):
    """生成 ``< > <= >=``：相邻两两都要满足大小关系（spec §5 链式比较）。"""

    def compare(args):
        for left, right in zip(args, args[1:]):
            if not predicate(_compare_order(left, right, who)):
                return False
        return True

    return compare


def _builtin_equals(args):
    """``=``：相邻两两等值即为真。

    刻意不走「比较大小」那条路：``=`` 只需要判等，遇到布尔或不同类型时
    直接给出 #f 而不是报错（spec §10 说明出错行为未定义，从宽处理更稳）。
    """
    for left, right in zip(args, args[1:]):
        if not _same_for_equals(left, right):
            return False
    return True


# ---------------------------------------------------------------------------
# 列表
# ---------------------------------------------------------------------------

def _builtin_cons(args):
    return Pair(args[0], args[1])


def _builtin_car(args):
    return require_pair(args[0], "car").car


def _builtin_cdr(args):
    return require_pair(args[0], "cdr").cdr


def _builtin_list(args):
    return build_list(args)


def _builtin_length(args):
    chain = require_proper_list(args[0], "length")
    count = 0
    while chain is not EMPTY:
        count += 1
        chain = chain.cdr
    return count


def _builtin_append(args):
    """拼接若干列表；最后一个参数可以不是列表（此时它作为链尾）。"""
    if not args:
        return EMPTY
    pieces = []
    for arg in args[:-1]:
        require_proper_list(arg, "append")
        pieces.extend(pair_to_list(arg))
    return build_list(pieces, args[-1])


def _builtin_null(args):
    return args[0] is EMPTY


def _builtin_pair(args):
    return isinstance(args[0], Pair)


def _builtin_listp(args):
    return proper_list(args[0])


# ---------------------------------------------------------------------------
# 谓词
# ---------------------------------------------------------------------------

def _builtin_numberp(args):
    return is_number(args[0])


def _builtin_booleanp(args):
    return isinstance(args[0], bool)


def _builtin_symbolp(args):
    return isinstance(args[0], Symbol)


def _builtin_stringp(args):
    return isinstance(args[0], str)


def _builtin_procedurep(args):
    return is_procedure(args[0])


def _make_numeric_predicate(who: str, test):
    """生成 zero?/even?/odd? 这类「参数必须是数」的谓词。"""

    def predicate(args):
        value = require_number(args[0], who)
        return test(value)

    return predicate


def _builtin_eq(args):
    return scheme_eq(args[0], args[1])


def _builtin_equal(args):
    return scheme_equal(args[0], args[1])


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _builtin_display(args):
    """打印一个值（字符串不带引号），不换行；结果是「无值」（spec §5）。"""
    sys.stdout.write(to_display_string(args[0]))
    return None


def _builtin_newline(args):
    sys.stdout.write("\n")
    return None


# ---------------------------------------------------------------------------
# 注册表：符号名 → (实现, 最少参数, 最多参数)
# ---------------------------------------------------------------------------

# max_args 为 None 表示可变参数。
_PROCEDURES = [
    # 算术
    ("+", _builtin_add, 0, None),
    ("-", _builtin_sub, 1, None),
    ("*", _builtin_mul, 0, None),
    ("/", _builtin_div, 1, None),
    ("modulo", _builtin_modulo, 2, 2),
    ("quotient", _builtin_quotient, 2, 2),
    ("expt", _builtin_expt, 2, 2),
    ("abs", _builtin_abs, 1, 1),
    # 比较
    ("=", _builtin_equals, 1, None),
    ("<", _make_ordering("<", lambda order: order < 0), 1, None),
    (">", _make_ordering(">", lambda order: order > 0), 1, None),
    ("<=", _make_ordering("<=", lambda order: order <= 0), 1, None),
    (">=", _make_ordering(">=", lambda order: order >= 0), 1, None),
    # 布尔
    ("not", lambda args: not is_truthy(args[0]), 1, 1),
    # 列表
    ("cons", _builtin_cons, 2, 2),
    ("car", _builtin_car, 1, 1),
    ("cdr", _builtin_cdr, 1, 1),
    ("list", _builtin_list, 0, None),
    ("length", _builtin_length, 1, 1),
    ("append", _builtin_append, 0, None),
    ("null?", _builtin_null, 1, 1),
    ("pair?", _builtin_pair, 1, 1),
    ("list?", _builtin_listp, 1, 1),
    # 类型谓词
    ("number?", _builtin_numberp, 1, 1),
    ("boolean?", _builtin_booleanp, 1, 1),
    ("symbol?", _builtin_symbolp, 1, 1),
    ("string?", _builtin_stringp, 1, 1),
    ("procedure?", _builtin_procedurep, 1, 1),
    # 数值谓词
    ("zero?", _make_numeric_predicate("zero?", lambda value: value == 0), 1, 1),
    ("even?", _make_numeric_predicate("even?", lambda value: value % 2 == 0), 1, 1),
    ("odd?", _make_numeric_predicate("odd?", lambda value: value % 2 != 0), 1, 1),
    # 相等谓词
    ("eq?", _builtin_eq, 2, 2),
    ("equal?", _builtin_equal, 2, 2),
    # 输出
    ("display", _builtin_display, 1, 1),
    ("newline", _builtin_newline, 0, 0),
]


def make_global_env() -> Environment:
    """建一个只含内置过程的全局环境（每个测试用例的初始环境，spec §2）。"""
    env = Environment(parent=None, name="全局环境")
    for name, fn, min_args, max_args in _PROCEDURES:
        env.define(symbol(name), Builtin(name, fn, min_args, max_args))
    return env
