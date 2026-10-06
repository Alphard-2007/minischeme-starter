"""词法分析：程序文本 → 词（token）列表（README §4 流水线的第一步）。

职责边界：本模块**只**负责切词，不判断语法结构（那是 parser 的事），
也不做任何求值。切出来的 token 带行号，报错时能指出大概位置。

支持的零件（spec §3）：注释 ``;``、整数/浮点、布尔 ``#t``/``#f``、符号、
字符串（含 ``\\n`` ``\\t`` ``\\"`` ``\\\\`` 转义）、引用简写 ``'``、
圆括号，以及点对用的 ``.``。
"""

from __future__ import annotations

from typing import NamedTuple

from errors import SchemeSyntaxError

__all__ = ["Token", "tokenize"]

# token 的种类。atom 的 value 是原始文本（由 parser 决定它是数字还是符号），
# string 的 value 是已经处理好转义的字符串，bool 的 value 是 Python 布尔。
L_PAREN = "lparen"
R_PAREN = "rparen"
QUOTE = "quote"
DOT = "dot"
ATOM = "atom"
STRING = "string"
BOOL = "bool"


class Token(NamedTuple):
    """一个词：种类、载荷、所在行号。"""

    kind: str
    value: object
    line: int


# 这些字符会终止一个 atom；空白单独处理（因为要数行号）。
_DELIMITERS = frozenset("()\"';")
_WHITESPACE = frozenset(" \t\r\f\v")

# 字符串里允许的转义
_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    '"': '"',
    "\\": "\\",
}


def tokenize(text: str, source: str = "<string>") -> list[Token]:
    """把整段源码切成 token 列表。

    ``source`` 只用于错误信息里标明出自哪个文件。
    """
    tokens: list[Token] = []
    index = 0
    line = 1
    length = len(text)

    while index < length:
        char = text[index]

        # --- 换行与空白：跳过，换行要记行号 ---
        if char == "\n":
            line += 1
            index += 1
            continue
        if char in _WHITESPACE:
            index += 1
            continue

        # --- 注释：从 ; 吃到行尾 ---
        if char == ";":
            while index < length and text[index] != "\n":
                index += 1
            continue

        # --- 结构性单字符 token ---
        if char == "(":
            tokens.append(Token(L_PAREN, char, line))
            index += 1
            continue
        if char == ")":
            tokens.append(Token(R_PAREN, char, line))
            index += 1
            continue
        if char == "'":
            tokens.append(Token(QUOTE, char, line))
            index += 1
            continue

        # --- 字符串字面量 ---
        if char == '"':
            value, index = _read_string(text, index, length, line, source)
            tokens.append(Token(STRING, value, line))
            continue

        # --- 布尔字面量 #t / #f ---
        if char == "#":
            if index + 1 < length and text[index + 1] in ("t", "f"):
                tokens.append(Token(BOOL, text[index + 1] == "t", line))
                index += 2
                continue
            seen = text[index + 1] if index + 1 < length else "<文件结尾>"
            raise SchemeSyntaxError(f"{source} 第 {line} 行：无法识别的字面量 #{seen}（只支持 #t 和 #f）")

        # --- 普通 atom：一直吃到分隔符为止 ---
        start = index
        while index < length and text[index] not in _DELIMITERS and text[index] not in _WHITESPACE \
                and text[index] != "\n":
            index += 1
        word = text[start:index]
        tokens.append(Token(DOT if word == "." else ATOM, word, line))

    return tokens


def _read_string(text: str, index: int, length: int, line: int, source: str):
    """读取一个双引号字符串，返回（解码后的内容, 结束位置的下一个下标）。

    ``index`` 指向开头的引号。转义按 spec §3 处理。
    """
    index += 1  # 跳过开头的 "
    pieces: list[str] = []
    while True:
        if index >= length:
            raise SchemeSyntaxError(f"{source} 第 {line} 行：字符串缺少结束的引号")
        char = text[index]
        if char == '"':
            return "".join(pieces), index + 1
        if char == "\n":
            # 源码里直接换行说明引号没闭合，报错比默默吞掉更好排查
            raise SchemeSyntaxError(f"{source} 第 {line} 行：字符串缺少结束的引号")
        if char == "\\":
            if index + 1 >= length:
                raise SchemeSyntaxError(f"{source} 第 {line} 行：字符串以孤立的反斜杠结尾")
            escaped = text[index + 1]
            if escaped not in _ESCAPES:
                raise SchemeSyntaxError(
                    f"{source} 第 {line} 行：无法识别的转义 \\{escaped}（只支持 \\n \\t \\r \\\" \\\\）"
                )
            pieces.append(_ESCAPES[escaped])
            index += 2
            continue
        pieces.append(char)
        index += 1
