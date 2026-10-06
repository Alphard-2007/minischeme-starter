"""语法分析：token 列表 → 表达式（嵌套的数据结构）。

关键设计：**列表字面量在解析阶段就造成点对链**（``Pair``/``EMPTY``），
而不是先存成 Python 列表再转换。这样 ``'(1 2 3)`` 与 ``(list 1 2 3)``
天然是同一种数据表示，spec §11 里「引用数据没转成点对链」的坑就不存在了；
同时每次解析都新建对象，``(eq? '(1) '(1))`` 才会正确地得到 ``#f``。

表达式的四种可能形态：
- 自求值数据：``int`` / ``float`` / ``bool`` / ``str`` / ``EMPTY``
- 符号：``Symbol``
- 点对链（括号表达式）：``Pair``，其中 ``(quote x)`` 也是一条普通点对链
- 不存在其它形态
"""

from __future__ import annotations

from errors import SchemeSyntaxError
from lexer import ATOM, BOOL, DOT, L_PAREN, QUOTE, R_PAREN, STRING, Token
from values import EMPTY, Pair, build_list, parse_number_literal, symbol

__all__ = ["parse_program"]

_QUOTE_SYMBOL = symbol("quote")


class Parser:
    """递归下降解析器。一个实例只解析一段源码。"""

    def __init__(self, tokens: list[Token], source: str = "<string>") -> None:
        self._tokens = tokens
        self._source = source
        self._pos = 0

    # -- 对外接口 ---------------------------------------------------------

    def parse_program(self) -> list:
        """解析出全部顶层表达式（spec §2：按顺序逐个求值）。"""
        expressions = []
        while not self._at_end():
            expressions.append(self._parse_expression())
        return expressions

    # -- 内部工具 ---------------------------------------------------------

    def _at_end(self) -> bool:
        return self._pos >= len(self._tokens)

    def _peek(self):
        """看当前 token；到末尾返回 None。"""
        return None if self._at_end() else self._tokens[self._pos]

    def _advance(self) -> Token:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _where(self, line) -> str:
        return f"{self._source} 第 {line} 行"

    # -- 解析规则 ---------------------------------------------------------

    def _parse_expression(self):
        token = self._peek()
        if token is None:
            raise SchemeSyntaxError(f"{self._source}：程序在表达式中间就结束了")

        if token.kind == ATOM:
            self._advance()
            return self._atom_value(token)

        if token.kind in (STRING, BOOL):
            self._advance()
            return token.value

        if token.kind == QUOTE:
            # 'x 是 (quote x) 的简写（spec §4.1）。
            # 注意要再包一层列表：(quote x) 的参数表是「只含一个元素的列表」，
            # 否则 '(1 2 3) 会被当成 (quote 1 2 3)。
            self._advance()
            if self._at_end():
                raise SchemeSyntaxError(f"{self._where(token.line)}：' 后面缺少数据")
            return Pair(_QUOTE_SYMBOL, build_list([self._parse_expression()]))

        if token.kind == L_PAREN:
            self._advance()
            return self._parse_list(token)

        if token.kind == R_PAREN:
            raise SchemeSyntaxError(f"{self._where(token.line)}：多了一个右括号 )")

        # 只剩 DOT：单独的 . 不是合法表达式
        raise SchemeSyntaxError(f"{self._where(token.line)}：. 只能出现在点对写法 (a . b) 中")

    def _parse_list(self, open_token: Token):
        """解析 ``(`` 之后的内容，直到匹配的 ``)``，返回点对链。"""
        items: list = []
        tail = EMPTY  # 默认以空表结尾（真列表）
        while True:
            token = self._peek()
            if token is None:
                raise SchemeSyntaxError(
                    f"{self._where(open_token.line)}：括号没有闭合（缺少 )）"
                )
            if token.kind == R_PAREN:
                self._advance()
                return build_list(items, tail)
            if token.kind == DOT:
                # 点对写法 (a b . c)：. 之后必须正好跟一个表达式再跟 )
                self._advance()
                if self._at_end():
                    raise SchemeSyntaxError(f"{self._where(token.line)}：. 后面缺少数据")
                tail = self._parse_expression()
                closing = self._peek()
                if closing is None:
                    raise SchemeSyntaxError(f"{self._where(token.line)}：括号没有闭合（缺少 )）")
                if closing.kind != R_PAREN:
                    raise SchemeSyntaxError(
                        f"{self._where(closing.line)}：. 之后只能有一个表达式，然后是 )"
                    )
                self._advance()
                return build_list(items, tail)
            items.append(self._parse_expression())

    def _atom_value(self, token: Token):
        """把 atom 文本变成值：先试数字，否则当符号（大小写敏感）。"""
        number = parse_number_literal(token.value)
        if number is not None:
            return number
        return symbol(token.value)


def parse_program(tokens: list[Token], source: str = "<string>") -> list:
    """模块级入口：token 列表 → 顶层表达式列表。"""
    return Parser(tokens, source).parse_program()
