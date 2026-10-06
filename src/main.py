"""mini-Scheme 解释器入口。

用法（spec §2）::

    python3 src/main.py file1.scm [file2.scm ...]   # 依次运行若干文件
    python3 src/main.py                             # 没有参数时从标准输入读取

行为约定：
- 按顺序求值每个顶层表达式，**每个结果独占一行**打印；
- 结果为「无值」（``None``）时不打印，例如 ``display``/``newline`` 的结果；
- 多个文件**共享同一个全局环境**，后一个文件能看到前一个文件的 ``define``；
- 程序里的错误信息写到标准错误流，并以非 0 退出码结束，
  这样标准输出里只有解释结果，便于逐字节比对。
"""

from __future__ import annotations

import os
import sys
import threading

# 让「python src/main.py」这种运行方式能直接 import 同目录下的模块
# （评分器就是这么调用的），同时也兼容被当作包导入的情形。
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from primitives import make_global_env  # noqa: E402  （路径设置好之后再导入）
from errors import SchemeError  # noqa: E402
from evaluator import evaluate  # noqa: E402
from lexer import tokenize  # noqa: E402
from parser import parse_program  # noqa: E402
from printer import to_repr_string  # noqa: E402


def run_source(text: str, env, source: str) -> None:
    """读 → 算 → 打印：把一段源码的所有顶层表达式跑完。"""
    expressions = parse_program(tokenize(text, source), source)
    for expression in expressions:
        result = evaluate(expression, env)
        if result is not None:  # spec §2：无值不打印
            _write_line(to_repr_string(result))


def _write_line(text: str) -> None:
    """统一走 sys.stdout.write，保证输出顺序与换行符可控。"""
    sys.stdout.write(text + "\n")


def _read_source(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _main(argv: list[str]) -> int:
    # 输出统一用 \n，避免 Windows 上被翻译成 \r\n 导致逐字节比对失败
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", newline="\n")
            except (ValueError, OSError):
                pass  # 某些宿主环境下不可重配置，保持默认即可

    env = make_global_env()  # 每个用例一个全新的全局环境

    if len(argv) > 1:
        sources = [(path, _read_source(path)) for path in argv[1:]]
    else:
        # 没有文件参数：从标准输入读取整段程序
        sources = [("<stdin>", sys.stdin.read())]

    for source, text in sources:
        run_source(text, env, source)

    sys.stdout.flush()
    return 0


def _run_in_big_stack(argv: list[str]) -> int:
    """在大栈的线程里跑主逻辑，让深递归（如 (sum-to 10000)）不会栈溢出。

    解释器是递归下降 + 递归求值，Scheme 的一层调用对应 Python 的好几层帧，
    默认递归上限很容易撞到。放大栈空间再提高递归上限是最省事也最稳的做法。
    """
    sys.setrecursionlimit(300000)
    try:
        threading.stack_size(256 * 1024 * 1024)
    except (ValueError, RuntimeError):
        pass  # 平台不允许设置时退回默认栈

    outcome: dict = {}

    def target() -> None:
        try:
            outcome["code"] = _main(argv)
        except BaseException as exc:  # 交给主线程统一处理
            outcome["error"] = exc

    worker = threading.Thread(target=target)
    worker.start()
    worker.join()

    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("code", 0)


def main() -> int:
    try:
        return _run_in_big_stack(sys.argv)
    except SchemeError as exc:
        sys.stderr.write(f"错误：{exc}\n")
        sys.stderr.flush()
        return 1
    except RecursionError:
        sys.stderr.write("错误：递归层数过深\n")
        sys.stderr.flush()
        return 1
    except FileNotFoundError as exc:
        sys.stderr.write(f"错误：找不到文件 {exc.filename}\n")
        sys.stderr.flush()
        return 1
    except OSError as exc:
        sys.stderr.write(f"错误：无法读取输入（{exc}）\n")
        sys.stderr.flush()
        return 1


if __name__ == "__main__":
    sys.exit(main())
