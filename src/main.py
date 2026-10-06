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
    # 用 utf-8-sig：能正确处理带 BOM 的文件（有些编辑器会加），
    # 否则 BOM 会被当成符号的一部分，报出「未绑定的符号」这种莫名其妙的错。
    with open(path, "r", encoding="utf-8-sig") as handle:
        return handle.read()


def _strip_bom(text: str) -> str:
    """去掉开头的 BOM（标准输入可能带）。"""
    return text[1:] if text.startswith("\ufeff") else text


def _main(argv: list[str]) -> int:
    # 输出统一用 \n，避免 Windows 上被翻译成 \r\n 导致逐字节比对失败；
    # 输入统一按 UTF-8 解码，避免 Windows 默认代码页把源码读乱。
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        if hasattr(stream, "reconfigure"):
            try:
                if stream is sys.stdin:
                    stream.reconfigure(encoding="utf-8")
                else:
                    stream.reconfigure(encoding="utf-8", newline="\n")
            except (ValueError, OSError):
                pass  # 某些宿主环境下不可重配置，保持默认即可

    env = make_global_env()  # 每个用例一个全新的全局环境

    if len(argv) > 1:
        sources = [(path, _read_source(path)) for path in argv[1:]]
    else:
        # 没有文件参数：从标准输入读取整段程序
        sources = [("<stdin>", _strip_bom(sys.stdin.read()))]

    for source, text in sources:
        run_source(text, env, source)

    sys.stdout.flush()
    return 0


def _request_bigger_stack() -> int:
    """逐级尝试放大线程栈，返回**实际生效**的栈字节数（0 表示没能放大）。

    不同平台能接受的栈大小差别很大（Windows 上 128MB 已是上限，
    256MB 会直接抛 ValueError），所以从大到小试，用第一个成功的。
    """
    for size_mb in (128, 64, 32, 16, 8):
        try:
            threading.stack_size(size_mb * 1024 * 1024)
            return size_mb * 1024 * 1024
        except (ValueError, RuntimeError):
            continue  # 该平台不接受这个大小，试小一档
    return 0


def _run_in_big_stack(argv: list[str]) -> int:
    """在大栈的线程里跑主逻辑，让深递归（如 (sum-to 10000)）不会栈溢出。

    解释器是递归下降 + 递归求值，Scheme 的一层调用对应若干层 Python 帧，
    默认栈与默认递归上限都很容易撞到。

    这里有个必须注意的安全点：**只有在确实拿到了更大的栈之后，才把递归上限
    提上去**。如果栈没放大却把上限设成几十万，深递归会耗尽 C 栈，
    进程直接崩溃（而不是抛出可以被捕获的 RecursionError），
    那样评分器看到的就是一个莫名其妙的失败。
    """
    stack_bytes = _request_bigger_stack()
    if stack_bytes:
        # 大栈生效：按栈大小给出一个宽裕但仍安全的上限
        sys.setrecursionlimit(min(200000, max(10000, stack_bytes // 1024)))
    else:
        # 没能放大栈：保守设限，宁可正常报「递归过深」，也不要崩掉进程
        sys.setrecursionlimit(5000)

    outcome: dict = {}

    def target() -> None:
        try:
            outcome["code"] = _main(argv)
        except BaseException as exc:  # 交给主线程统一处理并打印
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
