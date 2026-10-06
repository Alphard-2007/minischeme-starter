"""环境：变量绑定表 + 指向外层环境的指针（词法作用域的关键）。

每个环境就是一层「作用域」：
- 全局环境放内置过程，以及用户在顶层 ``define`` 的名字；
- 每次调用函数（或进入 ``let``）都新建一个子环境，里面放参数/局部变量，
  子环境的 ``parent`` 指向**函数定义时**的环境——这就是闭包（spec §4.6、§9）。

查找名字时沿 parent 一层层往外找，找不到就报「未绑定」。
"""

from __future__ import annotations

from errors import SchemeNameError
from values import Symbol

__all__ = ["Environment"]


class Environment:
    """一层作用域。"""

    __slots__ = ("bindings", "parent", "name")

    def __init__(self, parent: "Environment | None" = None, name: str = "环境") -> None:
        self.bindings: dict[str, object] = {}
        self.parent = parent
        self.name = name  # 只用于调试信息

    def child(self, name: str = "局部环境") -> "Environment":
        """以当前环境为外层，新建一个子环境。"""
        return Environment(self, name)

    def define(self, sym: Symbol, value) -> None:
        """在**当前**这一层绑定名字（``define`` 的语义）。"""
        self.bindings[sym.name] = value

    def lookup(self, sym: Symbol):
        """沿作用域链向外查找名字的值；查不到就报错。"""
        env: Environment | None = self
        name = sym.name
        while env is not None:
            if name in env.bindings:
                return env.bindings[name]
            env = env.parent
        raise SchemeNameError(f"未绑定的符号：{name}")

    def __repr__(self) -> str:
        return f"<Environment {self.name}: {sorted(self.bindings)}>"
