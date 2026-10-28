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
does not read external records or infer scenarios.
"""
import ast
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
_project_root = os.environ.get("PROJECT_DIR") or os.environ.get("PROJECT_NAME")
if not _project_root:
    _project_name = os.environ.get("PROJECT_NAME")
    if _project_name and Path(_project_name).name != _project_name:
        raise ValueError("PROJECT_NAME 必须是单一目录名")
    _project_root = str(Path.cwd() / _project_name) if _project_name else os.getcwd()
PROJECT_ROOT = Path(_project_root).expanduser().resolve()
PAGES_DIR = PROJECT_ROOT / "pages"
TESTCASES_DIR = PROJECT_ROOT / "tests"
SPEC_DIR = PROJECT_ROOT / "spec"

# 框架骨架模板目录（与脚本同级的 templates/）
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
# POM 阶段由 LLM 按功能使用的脚手架模板，不在 --init 落盘
SEED_TEMPLATES = {"seed_page.py.template", "seed_test.py.template"}
# config.yaml 渲染占位符（仅这 4 个，其余 __xxx__ 为 Python 语法）
_PLACEHOLDERS = ("__BASE_URL__", "__TEST_USER__", "__BROWSER_TYPE__", "__HEADLESS__")

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

# 明确的定位器 API 误用：get_by_text 接收 "text=..." 前缀串永远零命中
# （文本参数须传纯文案；需要 text= 选择器时用 page.locator("text=...")）。
MISUSE_TOKENS = (
    'get_by_text("text=',
    "get_by_text('text=",
)
# 疑似"导航即存在"的外壳标签：用作 READY_LOCATOR 会早于异步内容返回
# （须改为 XHR/AJAX 完成后才出现的元素）。
EARLY_ANCHOR_LABELS = ("Cart", "Home", "Sign in", "Login", "Categories")


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
        spec = PROJECT_ROOT / spec
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
    """扫描 pages/*.py，报告「疑似未验证猜测」「疑似多匹配选择器」「API 误用」「早返回锚点」。

    规则：
      - 含 `TODO_VERIFY` 的行：合法占位，收集到「待验证清单」仅提示，不报错。
      - 含 `# 实测命中` 注释的行（或其紧邻上一行）：视为已实测，跳过脆弱猜测检查。
      - 命中 FRAGILE_TOKENS 但未实测、又非 TODO_VERIFY：列为「疑似未验证猜测」并失败。
      - 命中 MULTIMATCH_TOKENS（a[href= / ] a / :has-text( 等）：
        即使已标 `# 实测命中`（只证明存在、不证明唯一），只要未显式标 `# 唯一`
        （采集期已用 count()==1 验证），即列为「疑似多匹配风险」并失败。
      - 命中 MISUSE_TOKENS（`get_by_text("text=...`）"：API 误用，永远零命中，必须修正。
      - READY_LOCATOR 用 EARLY_ANCHOR_LABELS 中的外壳标签（如 text=Cart）：
        疑似早于异步内容返回的锚点，须改为 XHR 后出现的元素。
    返回 0=无问题（允许 TODO_VERIFY），1=存在上述任一疑似问题。
    """
    pages = sorted(PAGES_DIR.glob("*.py")) if PAGES_DIR.exists() else []
    if not pages:
        print(f"未找到页面对象：{PAGES_DIR}（无需检查）")
        return 0

    suspects: list[tuple[str, int, str, str]] = []
    todos: list[tuple[str, int, str]] = []
    misuse: list[tuple[str, int, str]] = []
    early_anchor: list[tuple[str, int, str]] = []
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

    # 定位器 API 误用扫描：get_by_text("text=...") 永远零命中（应传纯文案）。
    for pf in pages:
        for i, line in enumerate(pf.read_text(encoding="utf-8").splitlines(), 1):
            if "TODO_VERIFY" in line:
                continue
            for tok in MISUSE_TOKENS:
                if tok in line:
                    misuse.append((pf.name, i, line.strip()))
                    break
    # 早返回锚点扫描：READY_LOCATOR 用"导航即存在"的外壳标签（须改为 XHR 后出现元素）。
    for pf in pages:
        for i, line in enumerate(pf.read_text(encoding="utf-8").splitlines(), 1):
            m = re.search(r'READY_LOCATOR\s*=\s*["\']text=([^"\']+)["\']', line)
            if m and m.group(1) in EARLY_ANCHOR_LABELS:
                early_anchor.append((pf.name, i, line.strip()))

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
    if misuse:
        print(f"\n[定位器 API 误用 get_by_text(\"text=\")] 共 {len(misuse)} 处（永远零命中，必须修正）：")
        for name, ln, text in misuse:
            print(f"  - {name}:{ln}  {text[:90]}")
    if early_anchor:
        print(f"\n[疑似早返回锚点 READY_LOCATOR] 共 {len(early_anchor)} 处"
              f"（外壳标签导航即存在，须改为 XHR 后出现的元素）：")
        for name, ln, text in early_anchor:
            print(f"  - {name}:{ln}  {text[:90]}")
    if suspects or multimatch or misuse or early_anchor:
        print("\n修复：")
        print("  - 未验证猜测：用 Playwright MCP 实测命中真实节点，在 locator 上方加 `# 实测命中：<说明>`；或暂改 self.loc(\"TODO_VERIFY:<用途>\")。")
        print("  - 多匹配风险：精炼到唯一——优先改用 data-test 契约级 locator（如 [data-test='x']）；或按可见文案用 get_by_role(\"link\"/\"button\", name=<文案>, exact=True) / get_by_text(<纯文案>) 区分；已在采集期用 count()==1 验证的，在 locator 上方补 `# 唯一` 标注。")
        print("  - get_by_text 误用 text= 前缀：改为传纯文案 get_by_text(\"Favorites\")，或用 page.locator(\"text=Favorites\")。")
        print("  - 早返回锚点：READY_LOCATOR 改为 XHR/AJAX 完成后才出现的元素（如商品行 data-test='product-title'），勿用向导标题/页头常驻文案。")
        return 1
    print("\n✅ 未发现未验证的脆弱选择器猜测、多匹配风险、API 误用与早返回锚点（TODO_VERIFY 占位不计入失败）。")
    return 0


def _audit_locators() -> int:
    """审计 locator 采集是否满足五性质：按步骤(需求表覆盖)、不冗余(预算有界)、
    不猜测(均有实证)、稳定可靠(契约/语义级)、档位未降级(tier==max_tier)。

    契约文件（采集期须落盘）：spec/evidence/locators-<页>.json 与（可选）
    spec/evidence/locator-demands-<模块>.json。缺证据 JSON 时仅提示并做轻量
    抽查，不报错，便于渐进采用；证据 JSON 存在则执行完整结构/一致性/预算/覆盖校验。
    """
    import json

    evidence_dir = SPEC_DIR / "evidence"
    pages = sorted(PAGES_DIR.glob("*.py")) if PAGES_DIR.exists() else []
    errors: list[str] = []
    warns: list[str] = []

    def _load_json(p: Path):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None

    def _selector_in_pages(selector: str) -> bool:
        s = selector.strip().strip('"').strip("'")
        s = s.replace("page.locator(", "").rstrip(")")
        if not s:
            return False
        for pf in pages:
            try:
                txt = pf.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                continue
            if s in txt and "# 实测命中" in txt:
                return True
        return False

    if not evidence_dir.exists():
        warns.append(f"未找到证据目录 {evidence_dir}；建议采集期落盘 locators-<页>.json 以启用完整审计。")
    else:
        for pf in pages:
            if pf.name == "__init__.py":
                continue
            ev = evidence_dir / f"locators-{pf.stem}.json"
            if not ev.exists():
                warns.append(f"[缺证据] {pf.stem}_page.py 无对应 {ev.name}；采集期须落盘该页全部 locator 证据。")
                continue
            data = _load_json(ev)
            if data is None:
                errors.append(f"[证据损坏] {ev.name} 非合法 JSON")
                continue
            for loc in data.get("locators", []) or []:
                name = loc.get("name", "?")
                sel = loc.get("selector")
                if not sel:
                    errors.append(f"[证据缺字段] {ev.name} locator={name} 缺 selector")
                    continue
                tier = loc.get("tier")
                if tier not in ("contract", "semantic", "text"):
                    errors.append(f"[稳定性违规] {ev.name} locator={name} tier={tier!r}（structural 禁用，须 contract/semantic）")
                # 档位降级检测（G5）：tier 须等于该元素可达最高档 max_tier
                _RANK = {"contract": 3, "semantic": 2, "text": 1}
                if tier in _RANK:
                    max_tier = loc.get("max_tier")
                    if max_tier and _RANK.get(max_tier, 0) > _RANK[tier]:
                        warns.append(f"[档位降级] {ev.name} locator={name} tier={tier} 低于可达最高档 max_tier={max_tier}（须回流精炼到更高档）")
                    elif tier == "text":
                        warns.append(f"[档位降级] {ev.name} locator={name} 落到 text 级（最低稳档），须确认页面无 data-test/id/name/role 等更稳属性可替代，否则属降级")
                    # 证据 tier 与 selector 写法一致性
                    s = sel or ""
                    if tier == "contract" and ("get_by_text(" in s or "text=" in s):
                        errors.append(f"[证据错位] {ev.name} locator={name} tier=contract 但 selector 为文案级写法 {s!r}")
                    if tier == "text" and ("[data-test" in s or s.strip().startswith("#") or "get_by_test_id" in s):
                        warns.append(f"[档位不一致] {ev.name} locator={name} tier=text 但 selector 为稳定属性写法 {s!r}（tier 应置 contract/semantic）")
                if not loc.get("demand_id"):
                    errors.append(f"[越界/无来源] {ev.name} locator={name} 缺 demand_id（须回溯阶段0需求表）")
                if not loc.get("evidence"):
                    errors.append(f"[无实证] {ev.name} locator={name} 缺 evidence（须等价于 # 实测命中）")
                elif not _selector_in_pages(sel):
                    errors.append(f"[证据错位] {ev.name} locator={name} selector={sel!r} 未在 pages/*.py 中以 # 实测命中 出现")
            ops = data.get("operations", []) or []
            nav = sum(1 for o in ops if o.get("tool") == "navigate")
            html = sum(1 for o in ops if o.get("tool") == "get_visible_html")
            inter = sum(1 for o in ops if o.get("tool") in ("click", "fill", "hover", "press_key"))
            if (nav > 1 or html > 1) and not any(o.get("escalation_reason") for o in ops):
                warns.append(f"[预算提示] {ev.name} 多次 navigate/可见HTML 抽取，须为超额操作记录 escalation_reason（完整性优先的有界放宽）。")
            if inter > 5:
                errors.append(f"[操作冗余] {ev.name} 交互探测 {inter} 次 > 上限 5（每页仅暴露需求表内动态 DOM）")

    # 需求表覆盖审计（可选，存在才做）
    if evidence_dir.exists():
        demands = sorted(evidence_dir.glob("locator-demands-*.json"))
        if demands:
            required = set()
            for d in demands:
                for e in (_load_json(d) or []):
                    if e.get("required") and e.get("demand_id"):
                        required.add(e["demand_id"])
            covered = set()
            for pf in pages:
                if pf.name == "__init__.py":
                    continue
                ev = evidence_dir / f"locators-{pf.stem}.json"
                if ev.exists():
                    for loc in (_load_json(ev) or {}).get("locators", []) or []:
                        if loc.get("demand_id"):
                            covered.add(loc["demand_id"])
            for did in sorted(required - covered):
                errors.append(f"[覆盖缺口] 需求表必采项 {did} 无对应 locator（须补采或记录 blocked）")

    print("=" * 60)
    print("定位器采集审计（--audit-locators）")
    print("=" * 60)
    if warns:
        print(f"\n[提示] 共 {len(warns)} 处：")
        for w in warns:
            print(f"  - {w}")
    if errors:
        print(f"\n[错误] 共 {len(errors)} 处（须修复后重采）：")
        for e in errors:
            print(f"  - {e}")
        print("\n修复：补齐证据 JSON 字段 / 改用 contract 级 locator / 为超额操作补 escalation_reason；"
              "必采项缺失时回页面补 MCP 实测，禁止猜测。")
        return 1
    if warns:
        print("\n⚠️ 审计通过（含提示）：补齐上述证据 JSON 后，四性质校验将完全生效；当前仅做轻量抽查。")
        return 0
    print("\n✅ 定位器采集满足：按步骤(需求表覆盖)、不冗余(预算有界)、不猜测(均有实证)、稳定可靠(契约/语义级)、档位未降级(tier==max_tier)。")
    return 0


def _check_parametrize() -> int:
    """扫描 tests/test_*.py，拦截「用 for 循环代替 @pytest.mark.parametrize 的伪参数化」。

    规则：
      - 凡 test_ 函数体内含 `for x in <数据源>`（数据源为 test_data / _DATA / data[...] /
        _<NAME> 等数据矩阵引用，或 _DATA.get(...) / test_data[...] 调用），且该函数上方
        **无** @pytest.mark.parametrize 装饰，即判定为「伪参数化（for 循环代替）」，失败。
      - 交叉校验：若 spec/*.testcase.md 任一文件含 `[参数化]` 标记，但全部 tests 中未出现
        `@pytest.mark.parametrize`，亦判定失败（疑似漏参数化）。
    返回 0=通过，1=存在伪参数化 / 漏参数化。
    """
    tests = sorted(TESTCASES_DIR.glob("test_*.py")) if TESTCASES_DIR.exists() else []
    if not tests:
        print(f"未找到测试文件：{TESTCASES_DIR}（无需检查）")
        return 0

    _DATA_NAMES = {"test_data", "_DATA", "data"}

    def _is_param_dec(dec) -> bool:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            return dec.func.attr == "parametrize"
        if isinstance(dec, ast.Attribute):
            return dec.attr == "parametrize"
        return False

    def _iter_is_data(node: ast.AST) -> bool:
        if isinstance(node, ast.For):
            it = node.iter
            if isinstance(it, ast.Name) and it.id in _DATA_NAMES:
                return True
            if isinstance(it, ast.Subscript) and isinstance(it.value, ast.Name) \
                    and it.value.id in ("test_data", "data", "_DATA"):
                return True
            if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) \
                    and it.func.attr in ("get", "pop") \
                    and isinstance(it.func.value, ast.Name) \
                    and it.func.value.id in _DATA_NAMES:
                return True
        return False

    problems: list[tuple[str, int, str]] = []
    for tf in tests:
        try:
            tree = ast.parse(tf.read_text(encoding="utf-8"))
        except SyntaxError as e:
            print(f"  [跳过] {tf.name} 语法错误：{e}")
            continue
        for fn in (n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")):
            has_param = any(_is_param_dec(d) for d in fn.decorator_list)
            loops_data = any(_iter_is_data(n) for n in ast.walk(fn))
            if loops_data and not has_param:
                problems.append((tf.name, fn.lineno, fn.name))

    # 交叉校验：spec 标注 [参数化] 但 tests 无 parametrize
    spec_flagged = False
    if SPEC_DIR.exists():
        for sf in SPEC_DIR.glob("*.testcase.md"):
            if "[参数化]" in sf.read_text(encoding="utf-8"):
                spec_flagged = True
                break
    if spec_flagged and not any("parametrize" in tf.read_text(encoding="utf-8") for tf in tests):
        problems.append(("spec", 0, "存在 [参数化] 场景但无 @pytest.mark.parametrize"))

    print("=" * 60)
    print("参数化自检（--check-parametrize）")
    print("=" * 60)
    if not problems:
        print("\n✅ 未发现 for 循环代替 @pytest.mark.parametrize 的伪参数化。")
        return 0
    print(f"\n[伪参数化 / 漏参数化] 共 {len(problems)} 处"
          f"（必须用 @pytest.mark.parametrize 展开为独立测试节点）：")
    for name, ln, fn in problems:
        where = f"{name}:{ln}" if ln else name
        print(f"  - {where}  {fn}")
    print("\n修复：将数据矩阵在测试模块级加载"
          "（yaml.safe_load(.../data/...)），并用")
    print('      @pytest.mark.parametrize("row", [pytest.param(c, id=c["row_id"]) for c in _DATA["..."]])')
    print("      展开；删除函数体内的 for 遍历。详见 references/pom-generation.md 参数化小节。")
    return 1


def _render(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace(k, v)
    return text


def _init_framework(values: dict) -> int:
    """复制 templates/ 下全部框架骨架到 PROJECT_ROOT，渲染 config.yaml 占位符，建空目录。

    幂等：已存在的文件保留（不覆盖用户实现）。seed_* 脚手架不复制（POM 阶段按功能使用）。
    """
    if not TEMPLATES_DIR.is_dir():
        print(f"错误：templates 目录缺失：{TEMPLATES_DIR}")
        return 1
    copied = 0
    for tpl in sorted(TEMPLATES_DIR.rglob("*.template")):
        if tpl.name in SEED_TEMPLATES:
            continue  # 页面/测试脚手架由 LLM 在 POM 阶段按功能使用，不在 init 落盘
        rel = tpl.relative_to(TEMPLATES_DIR).with_suffix("")  # 去掉 .template：config.yaml / conftest.py 等
        dest = PROJECT_ROOT / rel
        if dest.exists():
            continue  # 幂等：保留已有文件
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = _render(tpl.read_text(encoding="utf-8"), values)
        # browser_types 支持逗号分隔多引擎，渲染为 YAML 列表（避免 ["chromium,firefox"] 单元素）
        bt_raw = values["__BROWSER_TYPE__"]
        if "," in bt_raw:
            lst = ", ".join(b.strip() for b in bt_raw.split(",") if b.strip())
            content = content.replace(f'["{bt_raw}"]', f'[{lst}]')
        dest.write_text(content, encoding="utf-8")
        copied += 1
        print(f"  生成：{dest.relative_to(PROJECT_ROOT)}")
    # 空目录 + 包初始化（pages/components 作为包，保证 from pages.x import 可用）
    for d in ("pages", "components", "data", "spec"):
        (PROJECT_ROOT / d).mkdir(parents=True, exist_ok=True)
    for pkg in ("pages", "components"):
        init_f = PROJECT_ROOT / pkg / "__init__.py"
        if not init_f.exists():
            init_f.write_text("", encoding="utf-8")
    print(f"\n框架初始化完成：{PROJECT_ROOT}（共生成 {copied} 个文件，占位符已渲染）")
    if not values["__BASE_URL__"]:
        print("提示：未提供 --base-url，请在 config/config.yaml 的 web.base_url 填写真实地址，否则运行会报错")
    print("下一步（POM 用例生成）：准备 spec/<模块>.testcase.md，"
          "再运行本脚本校验并按三步流程生成 pages/ 与 tests/。")
    return 0


def _init_framework_cmd(argv: list) -> int:
    parser = _argparse()
    ns, _ = parser.parse_known_args(argv)
    values = {
        "__BASE_URL__": ns.base_url or "",
        "__TEST_USER__": ns.test_user or "",
        "__BROWSER_TYPE__": ns.browser_type or "chromium",
        "__HEADLESS__": ns.headless or "true",
    }
    return _init_framework(values)


def _argparse():
    import argparse
    p = argparse.ArgumentParser(
        prog="run_generator.py",
        description="Playwright Web 框架初始化与 POM 用例生成器入口。")
    p.add_argument("--init", action="store_true", help="复制框架骨架模板到项目根（框架初始化模式）")
    p.add_argument("--base-url", default="", help="真实 Web 前台地址，渲染到 config.yaml 的 web.base_url")
    p.add_argument("--test-user", default="", help="测试账号用户名，渲染到 config.yaml 的 auth.test_user")
    p.add_argument("--browser-type", default="chromium",
                   help="浏览器引擎 chromium/firefox/webkit，可扩展为多种（如 chromium,firefox）")
    p.add_argument("--headless", default="true", help="是否无头模式 true/false")
    p.add_argument("--check-parametrize", action="store_true",
                   help="校验参数化用例是否误用 for 循环代替 @pytest.mark.parametrize")
    p.add_argument("--audit-locators", action="store_true",
                   help="审计 locator 采集五性质：按步骤(需求表覆盖)/不冗余(预算有界)/不猜测(均有实证)/稳定可靠(契约级)/档位未降级(tier==max_tier)")
    return p


def main() -> int:
    if len(sys.argv) < 2:
        print("用法:")
        print("  python run_generator.py <模块>.testcase.md   # 单模块（推荐）")
        print("  python run_generator.py <任意名>              # 自动扫描 spec 下全部 *.testcase.md")
        print("  python run_generator.py --init [--base-url ... --test-user ... --browser-type chromium --headless true]  # 框架初始化")
        print("  python run_generator.py --check-locators               # 扫描页面对象定位器猜测")
        print("  python run_generator.py --check-parametrize            # 拦截 for 循环代替 @pytest.mark.parametrize")
        print("  python run_generator.py --audit-locators               # 审计定位器采集四性质(按步骤/不冗余/不猜测/稳定可靠)")
        return 1

    if sys.argv[1] == "--init":
        return _init_framework_cmd(sys.argv[2:])

    arg = sys.argv[1]
    if arg == "--check-locators":
        return _check_locators()
    if arg == "--check-parametrize":
        return _check_parametrize()
    if arg == "--audit-locators":
        return _audit_locators()
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
