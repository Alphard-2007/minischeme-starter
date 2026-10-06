"""自查脚本：在仓库根目录运行 ``python tests/run_tests.py``。

它做四件事，全部通过才算「自查通过」：

1. **格式比对**：跑 ``tests/format.scm``，把标准输出与
   ``tests/format.expected.txt`` **逐字节**比对（和评分器同样的比对方式）。
2. **值层面自查**：跑 ``tests/selftest.scm``。那份程序用 mini-Scheme 自己写的
   ``check`` 逐条比对，通过时不打印，失败时打印 ``FAIL ...``；
   期望输出只有 ``selftest done``。
3. **CLI 约定**（spec §2）：多文件共享全局环境、无参数时读标准输入。
4. **示例回归**：跑 ``example/`` 下六个示例，确认都能正常结束不报错。

退出码 0 表示全部通过；非 0 表示有项目失败，细节打印在屏幕上。
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join("src", "main.py")


def run_interpreter(args, stdin_text=None):
    """调用解释器，返回 (退出码, 标准输出, 标准错误)。

    刻意以**字节**方式捕获再解码：文本模式会做换行符转换，
    那样即使解释器错误地输出了 ``\\r\\n`` 也会被悄悄抹平，比对就失去意义。
    """
    proc = subprocess.run(
        [sys.executable, MAIN, *args],
        cwd=ROOT,
        input=stdin_text.encode("utf-8") if stdin_text is not None else None,
        capture_output=True,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    return proc.returncode, out, err


def _compare_with_expected(script: str, expected_name: str, title: str) -> bool:
    """通用比对：跑一个 .scm，把标准输出与同名期望文件逐字节比对。"""
    expected_path = os.path.join(ROOT, "tests", expected_name)
    with open(expected_path, "r", encoding="utf-8", newline="") as handle:
        expected = handle.read()

    code, out, err = run_interpreter([os.path.join("tests", script)])
    if code != 0:
        print(f"[FAIL] {title}：解释器退出码 {code}\n{err}")
        return False
    if out != expected:
        print(f"[FAIL] {title}：输出与期望不一致")
        _diff(expected, out)
        return False
    print(f"[PASS] {title}")
    return True


def check_format() -> bool:
    """比对 tests/format.scm 的输出与期望文件（打印形式，spec §8）。"""
    return _compare_with_expected(
        "format.scm", "format.expected.txt", "格式比对（逐字节）"
    )


def check_robust() -> bool:
    """比对 tests/robust.scm 的输出与期望文件（深递归与边界表达式）。"""
    return _compare_with_expected(
        "robust.scm", "robust.expected.txt", "鲁棒性自查（深递归与边界情形）"
    )


def _diff(expected: str, actual: str) -> None:
    expected_lines = expected.split("\n")
    actual_lines = actual.split("\n")
    for index in range(max(len(expected_lines), len(actual_lines))):
        want = expected_lines[index] if index < len(expected_lines) else "<无此行>"
        got = actual_lines[index] if index < len(actual_lines) else "<无此行>"
        if want != got:
            print(f"    第 {index + 1} 行：期望 {want!r}，实际 {got!r}")


def check_selftest() -> bool:
    """跑值层面自查，要求输出里没有任何 FAIL 行，且最后一行是 selftest done。

    注意：``define`` 在顶层会打印被定义的符号名（spec §4.5 的正常现象），
    所以这里不要求输出只有 ``selftest done``，只以「有没有 FAIL 行」为准。
    """
    code, out, err = run_interpreter([os.path.join("tests", "selftest.scm")])
    failures = [line for line in out.split("\n") if line.startswith("FAIL")]
    if code != 0:
        print(f"[FAIL] 值自查：解释器退出码 {code}\n{err}")
        return False
    if failures:
        print(f"[FAIL] 值自查：{len(failures)} 条不通过")
        for line in failures:
            print(f"    {line}")
        return False
    if out.rstrip("\n").split("\n")[-1] != "selftest done":
        print(f"[FAIL] 值自查：未跑到结尾（最后一行不是 selftest done）\n{err}")
        return False
    print("[PASS] 值层面自查（spec 各特性逐条比对）")
    return True


def check_cli() -> bool:
    """验证 spec §2 的命令行约定。"""
    ok = True

    # 多文件共享同一个全局环境：后一个文件能看到前一个文件的 define
    first = os.path.join("tests", "_cli_a.scm")
    second = os.path.join("tests", "_cli_b.scm")
    with open(first, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("(define shared-x 21)\n")
    with open(second, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("(* shared-x 2)\n")
    try:
        code, out, err = run_interpreter([first, second])
        expected = "shared-x\n42\n"
        if code != 0 or out != expected:
            print(f"[FAIL] 多文件共享环境：退出码 {code}，输出 {out!r}，错误 {err!r}")
            ok = False
        else:
            print("[PASS] CLI：多文件共享全局环境")
    finally:
        for path in (first, second):
            if os.path.exists(path):
                os.remove(path)

    # 无参数时从标准输入读取
    code, out, err = run_interpreter([], stdin_text="(+ 1 2)\n(display \"hi\")\n(newline)\n")
    if code != 0 or out != "3\nhi\n":
        print(f"[FAIL] 标准输入模式：退出码 {code}，输出 {out!r}，错误 {err!r}")
        ok = False
    else:
        print("[PASS] CLI：无参数时读标准输入")

    # 错误信息走 stderr，不污染 stdout
    code, out, err = run_interpreter([], stdin_text="(car 5)\n")
    if code == 0 or out != "" or not err:
        print(f"[FAIL] 错误处理：退出码 {code}，stdout {out!r}，stderr {err!r}")
        ok = False
    else:
        print("[PASS] 错误信息走 stderr，stdout 保持干净")

    return ok


def check_examples() -> bool:
    """六个示例都应正常跑完（输出内容已在开发时人工逐行核对）。"""
    example_dir = os.path.join(ROOT, "example")
    names = sorted(name for name in os.listdir(example_dir) if name.endswith(".scm"))
    if not names:
        print("[FAIL] 示例回归：example/ 下没有找到 .scm 文件")
        return False
    ok = True
    for name in names:
        code, _out, err = run_interpreter([os.path.join("example", name)])
        if code != 0:
            print(f"[FAIL] 示例 {name}：退出码 {code}\n{err}")
            ok = False
    if ok:
        print(f"[PASS] 示例回归（{len(names)} 个示例均正常运行）")
    return ok


def main() -> int:
    results = [
        check_format(),
        check_selftest(),
        check_robust(),
        check_cli(),
        check_examples(),
    ]
    print()
    if all(results):
        print("自查全部通过")
        return 0
    print("自查存在失败项")
    return 1


if __name__ == "__main__":
    sys.exit(main())
