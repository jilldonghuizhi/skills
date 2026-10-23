#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Planner 骨架脚本：检查 Explorer 探索记录存在并创建单份业务流程记录骨架。

独立可用，也被 playwright-pipeline-skill 串联调用。
数据流边界：Planner 直接读取 explorer.md（Explorer 产物），
不再经 Explorer Review 中转。本脚本启动前检查探索记录存在且可读，
否则拒绝创建业务流程骨架。
LLM 依据探索记录完成业务梳理；本脚本只创建空白模板，
不生成测试计划、用例或代码。
项目目录优先从 PROJECT_DIR 读取；旧变量 E2E_ROOT 保留兼容。
唯一产物为 <PROJECT_DIR>/spec/business_flow.md。
目标记录已存在时不覆盖，由 Planner 按增量规则维护，并重读最新探索记录。
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Windows 控制台可能为 cp1252/gbk，避免中文提示触发 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 自包含配置（独立 skill，不依赖编排器）
_project_root = os.environ.get("PROJECT_DIR") or os.environ.get("E2E_ROOT")
if not _project_root:
    _project_name = os.environ.get("PROJECT_NAME")
    if _project_name and Path(_project_name).name != _project_name:
        raise ValueError("PROJECT_NAME 必须是单一目录名")
    _project_root = str(Path.cwd() / _project_name) if _project_name else os.getcwd()
PROJECT_DIR = Path(_project_root).expanduser().resolve()
SPECS_DIR = PROJECT_DIR / "spec"


def main() -> int:
    if len(sys.argv) < 2:
        print('用法: python run_planner.py "<需求>" [<PROJECT_DIR>\\spec\\business_flow.md] [feature名]')
        return 1
    if len(sys.argv) > 4:
        print("错误：参数过多")
        return 1

    requirement = sys.argv[1]
    feature = sys.argv[3] if len(sys.argv) > 3 else "feature"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", feature):
        print(f"错误：feature 名称仅支持字母、数字、下划线和连字符：{feature}")
        return 1

    out = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else SPECS_DIR / "business_flow.md"
    )
    if not out.is_absolute():
        out = PROJECT_DIR / out
    out = out.resolve()
    try:
        out.relative_to(SPECS_DIR.resolve())
    except ValueError:
        print(f"错误：业务流程文档必须位于项目 spec 目录中：{SPECS_DIR}")
        return 1
    if not re.fullmatch(
        r"business_flow(?:_v[1-9][0-9]*)?\.md",
        out.name,
    ):
        print(
            "错误：Planner 只维护 business_flow.md（或显式版本 business_flow_vN.md）"
        )
        return 1

    # 前置检查：探索记录存在且可读；Planner 直接读取 _explore.md。
    explore_path = SPECS_DIR / "explorer.md"
    if not explore_path.is_file():
        print(f"错误：缺少 Explorer 探索记录：{explore_path}")
        print("Planner 唯一事实输入为 Explorer 探索记录，请先由 playwright-explorer-skill 完成探索。")
        return 1
    try:
        explore_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"错误：无法读取探索记录 {explore_path}：{exc}")
        return 1

    if out.exists():
        if not out.is_file():
            print(f"错误：业务流程文档目标不是文件：{out}")
            return 1
        print(f"检测到既有业务流程文档: {out}")
        print("未覆盖文件。请先重读最新探索记录，再按 Planner Skill 增量更新：")
        print("保留已有结论与来源；事实缺口直接回流 Explorer 补测（补测由 Explorer 执行），探索记录更新后再同步修订本文档。")
        return 0

    content = f"""# {requirement}业务流程
feature: {feature}
生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}
事实输入: {explore_path.name}（Planner 直接读取 explorer.md，不经过 Explorer Review）

## 1. 业务目标
- 目标：{requirement}
- 本次梳理范围：
- 输入来源：用户目标 + Explorer 探索记录：

## 2. 角色与进入条件
| 角色 | 进入条件/前置状态 | 可确认的权限 | 来源事实（REC） |
|---|---|---|---|

## 3. 主流程
| 步骤 | 用户动作 | 页面响应 | 业务状态变化 | 来源事实（REC-xxx） | 证据状态/缺口 |
|---|---|---|---|---|---|

## 4. 强制分支
| 分支类别 | 触发条件/动作 | 页面响应或状态变化 | 进入后续设计？ | 理由与来源事实/REC | 未知点 |
|---|---|---|---|---|---|

## 5. 五类业务材料（不是覆盖维度）
1. 字段：
2. 状态：
3. 权限：
4. 数据：
5. 环境：

## 6. 风险
- 已观察风险：
- 证据不足或受阻风险：
- 禁止操作/副作用边界：

## 7. 待确认问题
| 问题 | 为什么影响流程/测试设计 | 关联 REC/保留项 | 建议由谁或哪个阶段确认 |
|---|---|---|---|

## 8. Generator 用例生成交接
仅描述从探索事实可直接转换成自动化实现的场景规格，不写代码。
未满足执行条件的场景保留但不得标为 READY（READY / NEEDS_CONFIRMATION / BLOCKED）。
每个场景必须标注优先级（P0 / P1 / P2）及可追溯的判定理由，不得留空。

### 场景规格
| 字段 | 内容 |
|---|---|
| 场景 ID / 名称 | 稳定 ID（如 FLOW-01）及单一、可判定的场景目标 |
| 优先级 | P0 / P1 / P2，并给出一句可追溯的判定理由；不得留空 |
| 就绪状态 | READY / NEEDS_CONFIRMATION / BLOCKED，并给出简短理由 |
| 角色与初始状态 | |
| 前置条件 | |
| 测试数据 | 只引用环境变量名，不写真实凭据或个人数据 |
| 操作步骤 | 逐步关联主流程步骤、REC 与控件语义线索 |
| 预期结果（断言依据） | 断言目标 + 判定谓词 + 预期值；引用 REC 与结果元素线索 |
| 清理与副作用 | |
| 覆盖标签 | |
| 追溯来源 | 仅限探索记录中的 REC |

### 优先级规则
| 优先级 | 判定标准（满足任一即归为该级，取最高者） |
| --- | --- |
| P0 | 主流程正向路径或关键页面连接；权限/认证拦截与回跳；核心业务对象写入或状态变更（已获授权且可重复）；失败会阻塞其他场景的前置性场景 |
| P1 | 空态/无结果、字段必填与边界、数据与状态限制；列表筛选、搜索、分页、tab 切换等改变结果集的交互；有 fact + verified 支撑的异常与重复操作分支 |
| P2 | 辅助/可选只读路径与展示类页面；与主流程弱相关的补充观察；重复覆盖的次要变体 |

约束：优先级只决定生成与执行顺序，不改变就绪状态；BLOCKED / NEEDS_CONFIRMATION 同样要标注优先级；同一主流程步骤派生的场景不得全部标为 P0；无证据支撑业务重要性的默认 P2 并说明理由。

### 场景优先级汇总
| 场景 ID | 优先级 | 就绪状态 | 一句话判定理由 | 追溯来源 |
|---|---|---|---|---|
"""

    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as record:
            record.write(content)
    except FileExistsError:
        print(f"检测到并发创建的业务流程文档，未覆盖文件：{out}")
        print("请读取既有文档并按 Planner Skill 增量更新。")
        return 0
    except OSError as exc:
        print(f"错误：无法创建业务流程文档 {out}：{exc}")
        return 1

    print(f"业务流程骨架已生成: {out}")
    print("唯一产物：业务流程文档骨架；本脚本不执行探索、不生成测试计划/用例/代码。")
    print("下一步：仅依据探索记录完成梳理（每个场景标注优先级），再交由 playwright-plan-review-skill 审核。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
