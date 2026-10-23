#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Healer 脚本（步骤5）：执行 pytest，失败时重试（LLM 介入修复）。

独立可用，也被 playwright-pipeline-skill 串联调用。
LLM 承担实际诊断修复智能（读 pytest 失败日志与 e2e/traces/ 的 trace，
修复定位器/等待/断言），本脚本为编排骨架：调用 pytest + 重试循环。
"""
import os
import re
import subprocess
import sys
from pathlib import Path

# 自包含配置（独立 skill，不依赖编排器）
_project_root = os.environ.get("PROJECT_DIR") or os.environ.get("E2E_ROOT")
if not _project_root:
    _project_name = os.environ.get("PROJECT_NAME")
    if _project_name and Path(_project_name).name != _project_name:
        raise ValueError("PROJECT_NAME 必须是单一目录名")
    _project_root = str(Path.cwd() / _project_name) if _project_name else os.getcwd()
E2E_ROOT = Path(_project_root).expanduser().resolve()
MAX_HEAL_ATTEMPTS = int(os.environ.get("MAX_HEAL_ATTEMPTS", "3"))

USAGE = (
    "用法: python run_healer.py <测试文件|目录> [最大重试次数] "
    "[--user <账号>] [--pass <密码>] [额外 pytest 参数 ...]\n"
    "凭据：命令行 --user/--pass 优先，其次 NOVEL_USER/NOVEL_PASS 环境变量"
    "（以项目 fixture 实现为准）；凭据不写入文件与日志"
)


def _take_value(argv: list, i: int) -> tuple:
    """返回 (值, 下一索引)：支持 ``--opt value`` 与 ``--opt=value`` 两种形式。"""
    arg = argv[i]
    if "=" in arg:
        return arg.split("=", 1)[1], i + 1
    if i + 1 < len(argv):
        return argv[i + 1], i + 2
    return None, i + 1


def parse_cli(argv: list) -> dict:
    """解析命令行参数。

    - 位置参数：<测试路径> [最大重试次数]
    - 凭据快捷项：``--user``/``--pass``（alias ``--password``）转为 pytest
      选项 ``--user=``/``--password=``，由项目 conftest 的 ``pytest_addoption``
      注册的同名选项接收
    - 其余未知参数原样透传给 pytest；``--`` 之后的参数全部强制透传
    """
    test_path = None
    max_attempts = None
    pytest_args = []
    user = None
    password = None
    force_passthrough = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if force_passthrough:
            pytest_args.append(arg)
            i += 1
            continue
        if arg == "--":
            force_passthrough = True
            i += 1
            continue
        if arg == "--user" or arg.startswith("--user="):
            user, i = _take_value(argv, i)
            continue
        if (arg in ("--pass", "--password")
                or arg.startswith("--pass=") or arg.startswith("--password=")):
            password, i = _take_value(argv, i)
            continue
        if test_path is None and not arg.startswith("-"):
            test_path = arg
        elif max_attempts is None and not arg.startswith("-") and arg.isdigit():
            max_attempts = int(arg)
        else:
            pytest_args.append(arg)
        i += 1

    return {
        "test_path": test_path,
        "max_attempts": max_attempts,
        "pytest_args": pytest_args,
        "user": user,
        "password": password,
    }


def run_pytest(test_path: Path, pytest_args: list = None) -> tuple:
    """执行 pytest，返回 (退出码, stdout+stderr)。

    pytest_args：透传给 pytest 的额外参数（如 --user= / --password=，由项目
    conftest 注册；或原生 pytest 选项如 -k / -m）。凭据不会出现在任何输出中。
    """
    env = os.environ.copy()
    cmd = [sys.executable, "-m", "pytest", str(test_path), "-s",
           "--alluredir=allure-results"]
    cmd += list(pytest_args or [])
    result = subprocess.run(cmd, cwd=str(E2E_ROOT), capture_output=True,
                            text=True, env=env)
    return result.returncode, result.stdout + result.stderr


def parse_failed_tests(output: str) -> list:
    """从 pytest 输出中提取失败的用例名。"""
    failed = []
    # 匹配类似 FAILED test_home.py::TestHome::test_s1_首页标题 的行
    for line in output.splitlines():
        if line.strip().startswith("FAILED"):
            match = re.search(r'FAILED\s+(\S+)', line)
            if match:
                failed.append(match.group(1))
    return failed


def analyze_failure_log(output: str) -> str:
    """分析错误日志，提取关键错误信息供 LLM 诊断。"""
    summary = []

    # 提取 AssertionError
    summary.append("=== ASSERTION ERRORS ===")
    for line in output.splitlines():
        if "AssertionError" in line or "assert " in line.lower():
            summary.append(line)

    # 提取 Timeout/TimeoutError
    summary.append("\n=== TIMEOUT / TIMING ISSUES ===")
    for line in output.splitlines():
        if "timeout" in line.lower() or "timed out" in line.lower():
            summary.append(line)

    # 提取 Locator 相关错误
    summary.append("\n=== LOCATOR / ELEMENT ISSUES ===")
    for line in output.splitlines():
        if ("Locator" in line or "element" in line.lower() or
                "visible" in line.lower() or "clickable" in line.lower()):
            summary.append(line)

    # 提取最后 10 行 traceback
    summary.append("\n=== LAST 10 LINES OF TRACEBACK ===")
    lines = output.splitlines()
    summary.extend(lines[-10:] if len(lines) > 10 else lines)

    return "\n".join(summary) if summary else "无明确错误信息"


def main() -> int:
    opts = parse_cli(sys.argv[1:])

    if opts["test_path"] is None:
        print(USAGE)
        return 1

    test_path = Path(opts["test_path"])
    if not test_path.is_absolute():
        test_path = E2E_ROOT / test_path
    test_path = test_path.resolve()
    if not test_path.exists():
        print(f"错误：测试路径 {test_path} 不存在")
        return 1

    max_attempts = opts["max_attempts"] or MAX_HEAL_ATTEMPTS

    # 凭据快捷项 → pytest 选项（未提供则不追加，凭据来源由项目 fixture 决定）
    pytest_args = list(opts["pytest_args"])
    if opts["user"]:
        pytest_args.append(f"--user={opts['user']}")
    if opts["password"]:
        pytest_args.append(f"--password={opts['password']}")

    for attempt in range(1, max_attempts + 1):
        print(f"\n{'='*60}")
        print(f"第 {attempt}/{max_attempts} 次执行 pytest...")
        print(f"目标: {test_path}")
        print(f"根目录: {E2E_ROOT}")
        print(f"{'='*60}\n")

        rc, output = run_pytest(test_path, pytest_args)

        if rc == 0:
            print("\n✅ 测试通过！报告由 base_framework 的 conftest 收尾自动生成。")

            # 尝试生成 allure 结果摘要
            allure_results = E2E_ROOT / "allure-results"
            if allure_results.exists():
                files = list(allure_results.glob("*.json")) + list(allure_results.glob("*.txt"))
                print(f"Allure 结果文件数: {len(files)}")

            return 0

        print("\n❌ 测试失败，启动 Healer 诊断...\n")

        # 保存原始日志到文件（便于排查）；凭据不会出现在 pytest 输出中
        log_file = E2E_ROOT / f"healer_attempt_{attempt}.log"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(output)

        # 显示错误摘要
        error_summary = analyze_failure_log(output)
        print("错误摘要:")
        print(error_summary)

        # 提取失败的测试
        failed_tests = parse_failed_tests(output)
        if failed_tests:
            print(f"\n失败的测试: {failed_tests}")

        print(f"\n💡 LLM 需介入：读取 {log_file} 和 e2e/traces/ 进行分析与修复")
        print(f"   修复后请再次运行 healer 继续重试\n")

        # 如果不是首次失败，给人工修复留时间
        if attempt < max_attempts:
            try:
                input("按 Enter 键继续下一次重试，或 Ctrl+C 退出...")
            except KeyboardInterrupt:
                print("\n用户取消重试")
                return 1

    print(f"\n⚠️ 经 {max_attempts} 次修复后测试仍失败，请人工检查")
    return 1


if __name__ == "__main__":
    sys.exit(main())
