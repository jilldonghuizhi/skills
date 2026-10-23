#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Explorer 初始化脚本：创建或定位单份探索记录。

独立可用。
LLM 应用 Playwright MCP 探索真实站点并维护探索记录；本脚本只创建空白记录模板，
不执行浏览器操作、不审核探索结果，也不生成业务流程、测试计划、用例或代码。
项目目录默认取当前目录（根目录）；如需指定，可在目标项目目录下运行本脚本，或通过输出路径参数指明。未指定时直接在根目录的 spec/ 下创建。
唯一产物为 项目目录/spec/explorer.md（未指定项目目录时即当前根目录下的 spec/explorer.md）。
目标记录已存在时不覆盖，由 Explorer 按 Skill 的增量探索规则维护。

Skill 核心边界（探索阶段遵守，不在本脚本内执行）：
- 只观察、不获取 DOM：仅依据可见文本/交互行为/状态变化记录事实，不读取/解析选择器或层级路径；
- 凭据脱敏：不记录用户名/密码/令牌/验证码真实值，回显账号脱敏为 {{账号}}，截图/证据不含可还原凭据；
- 不编写业务流程、测试计划、用例、断言或代码。

用法:
    python run_explorer.py "<需求>"                      # 当前目录/spec/explorer.md
    python run_explorer.py "<需求>" <项目目录>            # <项目目录>/spec/explorer.md
    python run_explorer.py "<需求>" <路径>/explorer.md    # 显式输出路径（须位于 spec 目录）
    python run_explorer.py "<需求>" --base-url http://host

维护注意：下方模板为普通字符串，动态字段用 __REQUIREMENT__ / __GEN_TIME__ / __GEN_DATE__ / __BASE_URL__ 占位符经 .replace() 注入；
字面花括号（如脱敏占位 {{账号}}）原样保留，产物中亦为 `{{账号}}` 双花括号格式，无需转义。
"""
import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Windows 终端默认 cp1252：中文输出/reconfigure 失败时静默降级，不影响主流程
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 自包含配置（独立 skill）
# 项目目录：默认取当前目录（根目录）；如需指定，可在目标项目目录下运行本脚本，
# 或通过位置参数指明项目目录/输出路径。未指定时直接在根目录的 spec/ 下创建记录。
project_dir = Path.cwd().resolve()
BASE_URL = os.environ.get("BASE_URL", "")
SPECS_DIR = project_dir / "spec"

# 模板必须内置的插入标记（收口核对与逐条即时写入依赖它们）
REQUIRED_MARKERS = (
    "<!-- REC_INSERT_POINT -->",
    "<!-- PATH_INSERT_POINT -->",
    "<!-- EVIDENCE_INSERT_POINT -->",
    "<!-- QUESTION_INSERT_POINT -->",
    "<!-- GAP_INSERT_POINT -->",
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="初始化 Explorer 唯一记录 项目目录/spec/explorer.md（只建模板，不执行探索）"
    )
    parser.add_argument("requirement", help="本轮探索目标/需求（一句话）")
    parser.add_argument(
        "target",
        nargs="?",
        help="项目目录（在其下创建 spec/explorer.md）或显式输出 .md 路径；缺省为当前目录",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="被测地址（须来自用户授权/项目资料确认，不自行推断）；也可用环境变量 BASE_URL",
    )
    return parser


def resolve_output(target: str) -> Path:
    """target 为项目目录时落到 <目录>/spec/explorer.md；为 .md 文件时按显式输出路径。"""
    candidate = Path(target)
    out = candidate if candidate.suffix.lower() == ".md" else candidate / "spec" / "explorer.md"
    if not out.is_absolute():
        out = project_dir / out
    return out.resolve()


def main() -> int:
    args = build_arg_parser().parse_args()
    requirement = args.requirement.strip()
    if not requirement:
        print("错误：探索目标不能为空")
        return 1

    out = resolve_output(args.target) if args.target else SPECS_DIR / "explorer.md"
    try:
        out.relative_to(project_dir)
    except ValueError:
        print(f"错误：探索记录必须位于项目目录内：{project_dir}")
        return 1
    if out.parent.name != "spec":
        print(f"错误：探索记录必须位于项目 spec 目录中：{out.parent}")
        return 1
    if not re.fullmatch(
        r"explorer(?:_v[1-9][0-9]*)?\.md",
        out.name,
    ):
        print(
            "错误：Explorer 只维护 explorer.md（或显式版本 explorer_vN.md）"
        )
        return 1

    if out.exists():
        if not out.is_file():
            print(f"错误：探索记录目标不是文件：{out}")
            return 1
        print(f"检测到既有探索记录: {out}")
        print("未覆盖文件。请先读取头部「覆盖统计」与「已验证路径清单」，按 Explorer Skill 完成增量前置扫描：")
        print("保留旧 REC，新 REC 续编号；逐条即时写入（替换文件中的 INSERT_POINT 标记），追加增量轮次日志，刷新统计/路径清单/索引和缺口。")
        return 0

    now = datetime.now()
    base_url_text = args.base_url or "(探索时依据用户授权、项目资料或 config/config.yaml 确认；不得自行推断)"
    template = """# 探索记录：__REQUIREMENT__
生成时间: __GEN_TIME__
被测地址: __BASE_URL__

## 覆盖统计
- 已验证路径总数：0（仅统计证据状态为 verified 的 URL+入口+动作组合）
- 待处理项总数：0（question / blocked / candidate / contradicted 项数之和）
- 最近更新轮次：1（首次探索）

## 增量轮次
- 轮次 1 — __GEN_DATE__ — 触发：首次探索 | REC 范围：REC-001 起 | 说明：初始探索
<!-- 后续每轮追加一行：轮次 N — 日期 — 触发：新 Feature / 审核后定向补测 / Blocked 前置变化 | REC 范围：REC-xxx ~ REC-yyy -->

## 探索边界
- 目标：__REQUIREMENT__
- 环境：
- 范围与角色：
- 允许动作：
- 禁止动作：
- 停止条件：

## 页面与入口清单
| 页面 | URL/路由 | 入口 | 可见功能 |
| --- | --- | --- | --- |

## 已验证路径清单
仅收录证据状态为 verified 的路径，供增量前置扫描跳过；一行一个 URL+入口+动作组合：
| # | 角色 | URL/路由 | 入口 | 动作 | 结果摘要 | REC |
| --- | --- | --- | --- | --- | --- | --- |
<!-- PATH_INSERT_POINT -->

## 探索记录
按 REC-001 起连续编号；每条记录使用以下字段，并仅记录实际观察到的内容。
每条 REC 取证完成后立即写入此标记位置，不要积累后批量回填。
可标注「方法：<方法名>」说明本次探查由哪种测试设计方法驱动（等价类/边界值/判定表/因果图/场景/正交/状态迁移/错误猜测）；方法只决定探查样本，不生成用例或断言。
直接观察不含任何定位语义（按控件类型/可见文本/所在区块描述），不读取/记录 DOM、选择器或层级路径；凭据一律脱敏（回显账号记为 {{账号}}），不记录用户名/密码/令牌/验证码真实值。

<!-- REC_INSERT_POINT -->

## 覆盖范围
- 已探索页面/模块/角色：
- 已覆盖行为类别（按实际覆盖勾选，未覆盖留空并在下方说明原因）：
  - [ ] 目标主流程及关键页面连接
  - [ ] 角色与权限分支
  - [ ] 空态 / 无结果 / 缺失数据
  - [ ] 异常 / 边界行为
- 探索方法覆盖（用于选择探查样本，不生成用例；按需勾选已应用的方法）：
  - [ ] 等价类划分法
  - [ ] 边界值分析法
  - [ ] 判定表法
  - [ ] 因果图法
  - [ ] 场景法
  - [ ] 正交试验法
  - [ ] 状态迁移法
  - [ ] 错误猜测法
- 未覆盖范围及原因：

## 证据索引
| REC | 页面/动作 | 主张类型 | 证据状态 |
| --- | --- | --- | --- |
<!-- EVIDENCE_INSERT_POINT -->

## 疑点与待裁决项
| # | REC | 页面/动作 | 疑点/问题 | 待裁决事项 | 状态 |
| --- | --- | --- | --- | --- | --- |
<!-- QUESTION_INSERT_POINT -->

## 仍未探索的缺口
| # | REC | 缺口描述 | 类型 | 影响/原因 | 处置建议 |
| --- | --- | --- | --- | --- | --- |
<!-- GAP_INSERT_POINT -->
"""
    # 动态字段占位符注入；字面花括号（如脱敏占位 {{账号}}）原样保留，产物中亦为 {{账号}} 双花括号格式，无需转义
    content = (
        template
        .replace("__GEN_TIME__", now.strftime("%Y-%m-%d %H:%M:%S"))
        .replace("__GEN_DATE__", now.strftime("%Y-%m-%d"))
        .replace("__BASE_URL__", base_url_text)
        .replace("__REQUIREMENT__", requirement)
    )

    # 模板自检：标记齐全且脱敏占位符按 {{}} 双花括号格式原样渲染
    # 占位符格式检测：'{{账号}}' 须在产物中按双花括号存在，确认未退化为单花括号或遗漏
    missing = [m for m in REQUIRED_MARKERS if m not in content]
    if missing or "{{账号}}" not in content:
        print(f"错误：模板渲染异常，缺少 {missing or ['双花括号占位 {{账号}}']}；已中止，未写入文件")
        return 1

    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as record:
            record.write(content)
    except FileExistsError:
        print(f"检测到并发创建的探索记录，未覆盖文件：{out}")
        print("请读取既有记录并按 Explorer Skill 执行增量探索。")
        return 0
    except OSError as exc:
        print(f"错误：无法创建探索记录 {out}：{exc}")
        return 1

    print(f"探索记录模板已生成: {out}")
    print("唯一产物：探索记录模板；本脚本不执行探索或生成业务流程/测试计划/用例。")
    print("下一步：使用 Playwright MCP 按 Explorer Skill 完成探索。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
