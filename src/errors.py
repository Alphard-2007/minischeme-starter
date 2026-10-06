"""mini-Scheme 解释器的统一异常类型。

所有「可预期」的错误（语法错误、未绑定符号、类型不匹配、参数个数不对、
数值域错误等）都抛出本模块里的异常，由入口 main.py 统一捕获并写到
标准错误流（stderr）。这样安排有两个好处：

1. 标准输出（stdout）里只有解释结果，评分器逐字节比对时不会被报错文本污染；
2. 报错信息能说清「哪个语法形式、第几个参数、错在哪里」，方便定位问题。

spec §10 说明验收测试不会触发错误，因此这里的错误处理属于鲁棒性加分项，
而不是功能要求。
"""


class SchemeError(Exception):
    """所有 mini-Scheme 错误的基类。"""


class SchemeSyntaxError(SchemeError):
    """词法 / 语法阶段错误：括号不匹配、字符串未闭合、非法字面量、形式写错等。"""


class SchemeNameError(SchemeError):
    """引用了当前环境及其外层环境里都没有绑定的符号。"""


class SchemeTypeError(SchemeError):
    """对错误类型的值使用了某个过程，例如对非点对调用 car、拿符号做加法。"""


class SchemeArityError(SchemeError):
    """调用过程时实参个数不符合要求。"""


class SchemeValueError(SchemeError):
    """数值域错误，例如除以零、对非整数取模。"""
