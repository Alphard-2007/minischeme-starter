"""打印：值 → 文本（README §4 流水线的最后一步）。

两个入口对应 spec §8 的两种输出方式：
- ``to_repr_string``：顶层求值结果的打印形式，字符串**带**引号、转义可见；
- ``to_display_string``：``display`` 用的形式，字符串**不带**引号、转义还原成真字符。

其余类型（数字、布尔、符号、列表、点对、过程）两者一致。
打印点对时用「路径集合」做环检测：只在向下递归时记录祖先，
兄弟之间互不影响，所以共享子结构（例如 ``(list x x)``）能正常打印，
而真正的环会报错而不是卡死。
"""

from __future__ import annotations

from errors import SchemeError
from values import EMPTY, Builtin, Closure, Pair, Symbol, is_procedure

__all__ = ["to_display_string", "to_repr_string"]

# 需要转义的字符 → 打印形式
_ESCAPED = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\t": "\\t",
    "\r": "\\r",
}


def to_repr_string(value) -> str:
    """按 spec §8 的表格把值打印成文本（字符串带引号）。"""
    return _to_string(value, quoted=True, path=frozenset())


def to_display_string(value) -> str:
    """``display`` 用的打印形式（字符串不带引号）。"""
    return _to_string(value, quoted=False, path=frozenset())


def _to_string(value, quoted: bool, path: frozenset) -> str:
    # 「无值」正常情况下不会被打印（main 会跳过），这里兜底避免崩在打印环节。
    if value is None:
        return "#<none>"

    if value is EMPTY:
        return "()"

    # 布尔要排在数字前面判断：Python 里 bool 是 int 的子类。
    if isinstance(value, bool):
        return "#t" if value else "#f"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        return repr(value)  # 0.5 → '0.5'，与 spec §8 的例子一致

    if isinstance(value, Symbol):
        return value.name

    if isinstance(value, str):
        return _quote_string(value) if quoted else value

    if isinstance(value, Pair):
        return _pair_to_string(value, quoted, path)

    if is_procedure(value):
        return "#<procedure>"

    # 理论上到不了这里；留个明确的错误而不是打印出奇怪的东西。
    raise SchemeError(f"无法打印的值：{value!r}")


def _pair_to_string(pair: Pair, quoted: bool, path: frozenset) -> str:
    """把点对链打印成 ``(1 2 3)`` 或 ``(1 . 2)``。"""
    if id(pair) in path:
        raise SchemeError("检测到循环结构，无法打印")
    path = path | {id(pair)}

    parts = [_to_string(pair.car, quoted, path)]
    current = pair.cdr
    while True:
        if current is EMPTY:
            break
        if not isinstance(current, Pair):
            # 链尾不是空表 → 点对写法
            parts.append(".")
            parts.append(_to_string(current, quoted, path))
            break
        if id(current) in path:
            raise SchemeError("检测到循环结构，无法打印")
        path = path | {id(current)}
        parts.append(_to_string(current.car, quoted, path))
        current = current.cdr
    return "(" + " ".join(parts) + ")"


def _quote_string(text: str) -> str:
    """给字符串加引号，并把控制字符还原成 ``\\n`` 这类可见转义。"""
    pieces = ['"']
    for char in text:
        if char in _ESCAPED:
            pieces.append(_ESCAPED[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            pieces.append(f"\\x{ord(char):02x}")  # 其它不可见字符按十六进制转义
        else:
            pieces.append(char)
    pieces.append('"')
    return "".join(pieces)


# 让静态检查工具知道这些导入是被用到的（Builtin/Closure 通过 is_procedure 间接使用）
_ = (Builtin, Closure)
