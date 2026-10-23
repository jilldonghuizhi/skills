#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate POM inputs aligned with playwright-testcase-skill.

Input: playwright-testcase-skill per-module `<模块>.testcase.md`
(consumed by the LLM to generate one test_<功能>.py per module). The generator
does NOT read or fall back to `business_flow.md`; if no testcase module
files exist, it stops and reports.

Accepted arguments:
  * <模块>.testcase.md   -> single module (recommended)
  * <任意名>             -> auto-glob all *.testcase.md

The LLM applies only the supplied artifacts when implementing business behavior;
this helper validates the input path(s) and ensures output directories exist. It
does not read Explorer records or infer scenarios.
"""
import os
import re
import sys
from pathlib import Path

# Windows 控制台默认 cp1252 无法输出中文文件名，强制 UTF-8 输出
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover - 非 CPython/已配置时跳过
    pass

# 自包含配置（独立 skill，不依赖编排器）
_project_root = os.environ.get("PROJECT_DIR") or os.environ.get("E2E_ROOT")
if not _project_root:
    _project_name = os.environ.get("PROJECT_NAME")
    if _project_name and Path(_project_name).name != _project_name:
        raise ValueError("PROJECT_NAME 必须是单一目录名")
    _project_root = str(Path.cwd() / _project_name) if _project_name else os.getcwd()
E2E_ROOT = Path(_project_root).expanduser().resolve()
PAGES_DIR = E2E_ROOT / "e2e" / "pages"
TESTCASES_DIR = E2E_ROOT / "e2e" / "testcases"
SPEC_DIR = E2E_ROOT / "spec"

TESTCASE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\.testcase\.md$")
FEATURE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

# 易猜错的脆弱选择器类别（真实站点多用 layui/element 等组件库，结构随站点而定）。
# 这些 token 若出现在页面对象中却未标 `# 实测命中` 注释、也非 `TODO_VERIFY` 占位，
# 即为「疑似未验证猜测」，需在 MCP 实测后写入或改为 TODO_VERIFY。
FRAGILE_TOKENS = (
    "#pages", ".current", ".active", "下一页", "尾页",
    "#rankList", "#amountList", "#noResult", ".no-result",
    "#bookDetail", ".book-info", "#dialog", ".modal", ".layui-layer",
    "table tr",
)

# 易「一对多」命中（strict mode violation）的选择器特征：按属性/后代/文案模糊匹配，
# 同一目标 URL/文案常同时存在「页头文字链 + CTA 按钮」等多个节点。
# 即使已标 `# 实测命中`（只证明存在、不证明唯一），只要未显式标 `# 唯一`（采集期已用
# count()==1 验证），即视为「疑似多匹配风险」，须改用语义按名定位或补 `# 唯一` 标注。
MULTIMATCH_TOKENS = (
    "a[href=",     # 同 URL 的页头文字链 + CTA 按钮一对多（如 /user/register.html）
    "] a",         # 后代选择器（如 #nav a）易命中多个同结构节点
    ":has-text(",  # 文案模糊匹配易命中多个含该文案的节点
)


def _ensure_dirs() -> None:
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    TESTCASES_DIR.mkdir(parents=True, exist_ok=True)


def _validate_in_spec(spec: Path) -> None:
    try:
        spec.relative_to(SPEC_DIR.resolve())
    except ValueError:
        print(f"错误：输入必须位于项目目录的 spec 子目录中：{SPEC_DIR}")
        raise SystemExit(1)


def _feature_from_stem(stem: str) -> str:
    """testcase 模块文件名即模块名（已无 feature 前缀），直接返回。"""
    return stem


def _handle_feature(feature: str, override: str | None = None) -> int:
    if not FEATURE_RE.fullmatch(feature):
        print(f"错误：feature 名称仅支持字母、数字、下划线和连字符：{feature}")
        return 1
    if not SPEC_DIR.exists():
        print(f"错误：spec 目录不存在：{SPEC_DIR}")
        return 1
    modules = sorted(SPEC_DIR.glob("*.testcase.md"))
    modules = [m for m in modules if TESTCASE_RE.search(m.name)]
    if not modules:
        print(f"错误：spec 下未找到 {feature} 的 testcase 模块文件（*.testcase.md）。")
        print("      本 Skill 只消费 testcase.md，不读取/回退 business_flow.md。")
        return 1
    print(f"feature: {feature}")
    print(f"检测到 {len(modules)} 个 testcase 模块文件：")
    for m in modules:
        print(f"  - {m.name}")
    print("提示：LLM 按每个模块文件内「确定性 + READY」场景分别生成 test_<功能>.py；")
    print("      业务模块全名 → snake_case 功能名 由 LLM 派生（如 浏览发现→test_browse_discover.py）。")
    print("下一步：交由 playwright-code-review-skill 审核通过后再运行 pytest。")
    return 0


def _handle_module(spec: Path, override: str | None) -> int:
    if not spec.is_absolute():
        spec = E2E_ROOT / spec
    spec = spec.resolve()
    if not spec.exists():
        print(f"错误：testcase 模块文件 {spec} 不存在")
        return 1
    _validate_in_spec(spec)
    module = _feature_from_stem(spec.stem)
    print(f"模块: {module}")
    print(f"消费模块文件: {spec.name}")
    print("提示：LLM 按本模块文件内「确定性 + READY」场景生成对应 test_<功能>.py；")
    print("      @allure.feature 保留业务模块全名，用例 ID 沿用 <模块名>-<序号>。")
    print("下一步：交由 playwright-code-review-skill 审核通过后再运行 pytest。")
    return 0


def _check_locators() -> int:
    """扫描 e2e/pages/*.py，报告「疑似未验证猜测」与「疑似多匹配选择器」。

    规则：
      - 含 `TODO_VERIFY` 的行：合法占位，收集到「待验证清单」仅提示，不报错。
      - 含 `# 实测命中` 注释的行（或其紧邻上一行）：视为已实测，跳过脆弱猜测检查。
      - 命中 FRAGILE_TOKENS 但未实测、又非 TODO_VERIFY：列为「疑似未验证猜测」并失败。
      - 命中 MULTIMATCH_TOKENS（a[href= / ] a / :has-text( 等）：
        即使已标 `# 实测命中`（只证明存在、不证明唯一），只要未显式标 `# 唯一`
        （采集期已用 count()==1 验证），即列为「疑似多匹配风险」并失败。
    返回 0=无问题（允许 TODO_VERIFY），1=存在疑似猜测或多匹配风险。
    """
    pages = sorted(PAGES_DIR.glob("*.py")) if PAGES_DIR.exists() else []
    if not pages:
        print(f"未找到页面对象：{PAGES_DIR}（无需检查）")
        return 0

    suspects: list[tuple[str, int, str, str]] = []
    todos: list[tuple[str, int, str]] = []
    for pf in pages:
        prev = ""
        for i, line in enumerate(pf.read_text(encoding="utf-8").splitlines(), 1):
            if "TODO_VERIFY" in line:
                todos.append((pf.name, i, line.strip()))
                prev = line
                continue
            if "实测命中" in line or "实测命中" in prev:
                prev = line
                continue
            for tok in FRAGILE_TOKENS:
                if tok in line:
                    suspects.append((pf.name, i, tok, line.strip()))
                    break
            prev = line

    # 多匹配风险扫描：a[href= / ] a / :has-text( 等易一对多命中。
    # 即使已标 # 实测命中（只证明存在、不证明唯一），只要未显式标 # 唯一
    # （采集期已用 count()==1 验证）即判风险。TODO_VERIFY 占位不计入。
    multimatch: list[tuple[str, int, str, str]] = []
    for pf in pages:
        for i, line in enumerate(pf.read_text(encoding="utf-8").splitlines(), 1):
            if "TODO_VERIFY" in line or "# 唯一" in line or "#唯一" in line:
                continue
            for tok in MULTIMATCH_TOKENS:
                if tok in line:
                    multimatch.append((pf.name, i, tok, line.strip()))
                    break

    print("=" * 60)
    print("定位器自检（--check-locators）")
    print("=" * 60)
    if todos:
        print(f"\n[待验证占位 TODO_VERIFY] 共 {len(todos)} 处（合法，须在 Healer 阶段补实测）：")
        for name, ln, text in todos:
            print(f"  - {name}:{ln}  {text[:90]}")
    if suspects:
        print(f"\n[疑似未验证猜测] 共 {len(suspects)} 处（必须 MCP 实测后写入或改为 TODO_VERIFY）：")
        for name, ln, tok, text in suspects:
            print(f"  - {name}:{ln}  命中脆弱 token [{tok}]  ->  {text[:90]}")
    if multimatch:
        print(f"\n[疑似多匹配选择器] 共 {len(multimatch)} 处（须采集期用 count()==1 验证；"
              f"唯一则补 `# 唯一` 标注，否则改用语义按名定位 get_by_role(name=..., exact=True)）：")
        for name, ln, tok, text in multimatch:
            print(f"  - {name}:{ln}  命中多匹配风险 token [{tok}]  ->  {text[:90]}")
    if suspects or multimatch:
        print("\n修复：")
        print("  - 未验证猜测：用 Playwright MCP 实测命中真实节点，在 locator 上方加 `# 实测命中：<说明>`；或暂改 self.loc(\"TODO_VERIFY:<用途>\")。")
        print("  - 多匹配风险：精炼到唯一——按可见文案用 get_by_role(\"link\"/\"button\", name=<文案>, exact=True)")
        print("    或 get_by_text(<文案>) 区分；已在采集期用 count()==1 验证的，在 locator 上方补 `# 唯一` 标注。")
        return 1
    print("\n✅ 未发现未验证的脆弱选择器猜测与多匹配风险（TODO_VERIFY 占位不计入失败）。")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("用法:")
        print("  python run_generator.py <模块>.testcase.md   # 单模块（推荐）")
        print("  python run_generator.py <任意名>              # 自动扫描 spec 下全部 *.testcase.md")
        print("  python run_generator.py --check-locators               # 扫描页面对象定位器猜测")
        return 1

    arg = sys.argv[1]
    if arg == "--check-locators":
        return _check_locators()
    override = sys.argv[2] if len(sys.argv) > 2 else None
    _ensure_dirs()

    # 0) 显式拒绝 business_flow.md：本 Skill 只消费 testcase.md
    if "_business_flow" in arg:
        print("错误：本 Skill 只消费 <模块>.testcase.md，不接受 business_flow.md。")
        print("      请改用 testcase 模块文件，或传入任意名自动扫描 *.testcase.md。")
        return 1
    # 1) 单模块 testcase.md
    if TESTCASE_RE.search(arg):
        return _handle_module(Path(arg), override)
    # 2) 仅传 feature 名：自动 glob testcase 模块（不回退 business_flow.md）
    return _handle_feature(arg, override)


if __name__ == "__main__":
    sys.exit(main())
