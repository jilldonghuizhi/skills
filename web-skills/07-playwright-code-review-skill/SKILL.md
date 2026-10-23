---
name: playwright-code-review-skill
description: 生成的 POM 测试代码审核门禁（串联工作流阶段6）。审核 Generator 产出的页面对象与 pytest 用例；以通过 Explorer Review 和 Plan Review 的 business_flow.md 为唯一业务范围和断言依据。检查 POM、fixture、定位器、断言追溯和 py_compile/collect-only，通过才进 Healer 执行，不通过回 Generator 修订。
---

# 代码审核 Gate（阶段6）

## 🎯 角色与目标

你是一位高级测试开发工程师，在本阶段承担**代码审核 Gate** 角色：以审核通过的业务流程为唯一业务范围与断言依据，审核页面对象与用例的定位/断言封装、等待与导航策略、断言可追溯性与可运行性。

**定位与上下游**：Playwright 用例生成链路的第 6 阶段，门禁位于 Generator 与 Healer 之间：

**[playwright-explorer-skill 探索 → playwright-explorer-review-skill 审核 → playwright-planner-skill 梳理 → playwright-plan-review-skill 审核 → playwright-generator-skill 生成] → 本 skill（代码审核 Gate）→ [playwright-healer-skill 执行自愈]**

- **审核对象**：Generator 产出的多个 `e2e/pages/<page>_page.py`（一页一类）与 `e2e/testcases/test_<功能>.py`（多个功能文件，一功能一类一文件）+ `e2e/testcases/conftest.py`（共享 fixture）
- **Planner 链路的业务依据**：匹配且已审核通过的 `<PROJECT_DIR>/spec/business_flow.md`；不读取 Explorer 原文、聊天内容或原始需求来扩展/判定测试业务含义
- **可独立使用**：审核任意 POM 测试代码，不限来源
- **审核方**：用户人工为主，LLM 先行自检并提示用户确认

**意义**：在执行前拦截代码质量问题（POM 结构、fixture 误用、凭据硬编码），减少 Healer 无效重试消耗。

## 📋 前置条件与输入

### 1. 环境依赖
- 使用流水线上下文的 `PROJECT_DIR`（或用户明确指定的项目根）；所有相对路径均相对于该目录。
- 若审核 Generator 生成的代码，Planner 业务流程产物位于 `<PROJECT_DIR>/spec/business_flow.md`；页面对象、用例与共享 fixture 位于 `<PROJECT_DIR>/e2e/`。

### 2. 权限要求
- 只读取待审代码与 `business_flow.md`，不读取 Explorer 原文、聊天内容或原始需求来扩展/判定测试业务含义。
- 若 `PROJECT_DIR` 不明确，先请求用户提供项目根或明确的待审文件路径；不猜测、不扫描选择其他项目。
- 报告检查/语法检查从 `<PROJECT_DIR>` 执行；不得因目录约定不同而搬移或覆盖现有代码。

### 3. 必填输入
- 待审页面对象 `e2e/pages/<page>_page.py`、用例 `e2e/testcases/test_<功能>.py` 与共享 fixture `e2e/testcases/conftest.py`。
- 已审核通过的 `<PROJECT_DIR>/spec/business_flow.md`（Planner 链路场景与断言依据）。

### 4. 知识基线
- POM 结构与三步生成产物的验收标准；pytest 收集与 `py_compile` 可运行性。
- 断言可追溯性：每条用例断言须追溯到 `business_flow.md` 中对应 READY 场景的断言依据。

## 🚶 标准化工作流

### Step 1：环境预检（确定项目目录与审核范围）
- 确认 `PROJECT_DIR`（或用户指定的项目根）；不从 Skill 目录或当前任意工作目录寻找项目文件。
- 优先审核与 Planner READY 场景中页面清单对应的 `<PROJECT_DIR>/e2e/pages/` 页面类；用例与共享 fixture 分别位于 `<PROJECT_DIR>/e2e/testcases/`。
- 若 `PROJECT_DIR` 不明确，先请求用户提供项目根或明确的待审文件路径；不猜测、不扫描选择其他项目。

### Step 2：核心操作执行（LLM 自检 checklist）
逐项过以下 checklist，输出审查结论（通过 / 需修复 + 具体意见）：

**POM 结构**：
- **一页一类**：每个 `e2e/pages/<page>_page.py` 只含一个页面类，无多页面混塞；类数与计划"页面对象清单"一致
- **一功能一类一文件**：每个 `e2e/testcases/test_<功能>.py` 只含**一个** `class TestXxx`，无多功能 class 混塞；功能文件数 = 功能模块数；文件名 snake_case 与 class 名 PascalCase 对应（`test_home.py` → `TestHome`）
- 页面对象继承 `BasePage`（`from e2e.web.base_page import BasePage`），业务方法封装原子操作
- 跨页流程用例按需注入多个页面对象，同一 `page` 实例贯穿，未自建 browser

**三步生成产物**：
- 第 1 步骨架完成：无残留 `NotImplementedError`/`pass` 占位方法（除非计划标注该操作为缺口未实现）
- 第 2 步方法体已回填：每个方法有真实定位器与 BasePage 调用
- 第 3 步用例完整：每条生成用例对应 Planner 产物中的 READY 场景；每条断言均可追溯到该场景的断言依据，未自行加入 Planner 未提供的行为
- **用例功能文件拆分**：用例按功能模块拆分为独立 `test_<功能>.py` 文件（一功能一类一文件），**非单文件多 class** 亦**非扁平测试函数散落**；每个功能文件含一个 `class TestXxx`，跨功能场景按触发入口归属；class 无 `__init__`，fixture 经方法参数注入
- **共享 fixture 集中**：跨功能共享的 fixture（`header`/`home`/`common_layer`/`logged_in_page`/`_credentials` 等）统一放 `e2e/testcases/conftest.py`，各 `test_<功能>.py` 文件**未重复定义** fixture

**代码质量**：
- 定位器语义化（`get_by_role/get_by_label/get_by_placeholder/get_by_test_id`），无脆弱 CSS/XPath
- **用例层零 Playwright API**：`test_<功能>.py` 内不得出现 `page.locator(`/`get_by_`/`sync_api`/`expect(page`/`page.url`/`page.title()` 等原始定位/断言 API——定位与断言一律封装在页面对象方法内（状态读取方法返回纯值 + 用例原生 assert，或 `expect_xxx()` 断言封装）；URL/title 断言也经页面对象方法
- **等待与导航封装到位**：异步渲染内容（AJAX 表格/延迟文本）断言前有 `wait_for_xxx()`；触发导航的交互（普通链接/`javascript:` 伪协议/JS 导航 href/`location.reload()`）以 `expect_navigation` 包裹；`target="_blank"` 链接用 `context.expect_page()` 捕获新页返回；断言按真实 DOM 容器层级（不假设文本集中在单一元素）；无依赖站点数据分布的"值变化"断言（优先状态类断言）
- 用例用 conftest 的 `page` fixture，未自建 browser/context
- `@allure.feature` 标注在 **class 级**（一功能模块一 feature，与功能文件一一对应），`@allure.story`/`@allure.severity` 标注在**方法级**（每个测试场景一 story）
- 凭据经注入获取（pytest 命令行 `--user/--password` 或 `NOVEL_USER/NOVEL_PASS` 环境变量，任一来源即可），无明文硬编码
- `pytest --collect-only` 能收集全部新用例；`py_compile` 全过

### Step 3：结果格式化（门禁决策与结论）
1. 读生成的 `.py` 文件，逐项过 checklist，输出审查结论（通过 / 需修复 + 具体意见）。
2. 对 Planner 链路生成的代码，若 READY 场景缺失、代码无法映射至场景或业务断言超出 Planner 产物，标记为需修复并交回 Generator/Planner；不得自行读取 Explorer 或原始需求裁定缺失规则。提示用户人工确认后继续。
3. 门禁决策：
   - **通过** → 进 playwright-healer-skill 执行 pytest
   - **需修复** → 回 playwright-generator-skill 修订代码后重审（幂等：不覆盖用户手改内容，只补缺失项）

## ⚠️ 约束与规范

### 1. 代码规范（POM / 生成产物 / 代码质量）
- 一页一类、一功能一类一文件；页面对象继承 `BasePage`，业务方法封装原子操作。
- 三步生成产物完整、断言可追溯至 `business_flow.md` 的 READY 场景；共享 fixture 集中 conftest，用例层零 Playwright API。

### 2. 安全边界
- 业务依据仅限已审核的 `business_flow.md`；不读取 Explorer 原文、聊天内容或原始需求来扩展/裁定测试业务含义。
- 不得因目录约定不同而搬移或覆盖现有代码；`PROJECT_DIR` 不明确时不猜测、不扫描选择其他项目。

### 3. 性能约束
- 门禁为本地静态 + 收集检查，不实际执行 pytest；执行交由下游 Healer。

### 4. 输出规范（审查结论）
- 输出"通过"或"需修复 + 具体意见"；需修复项须指向 Generator/Planner 并说明缺失的场景映射或越界断言；提示用户人工确认后再继续。

## ✅ 验证与自查

### 1. 功能校验
- checklist（POM 结构 / 三步产物 / 代码质量）逐项全过；`py_compile` 与 `pytest --collect-only` 通过。

### 2. 完整性校验
- 每个页面类与功能文件齐备；每条用例断言可追溯到 `business_flow.md` 的对应 READY 场景；共享 fixture 无重复定义。

### 3. 常见错误排查
- 多功能 class 混塞或扁平测试函数散落（违反一功能一类一文件）。
- 用例层出现 `page.locator`/`get_by_` 等原始 Playwright API（未下沉到页面对象）。
- 断言无法追溯到 Planner 产物、或业务断言超出 Planner 提供的范围。
- 凭据明文硬编码。

### 4. 最终确认
- 门禁决策明确：通过 → Healer；需修复 → 回 Generator 修订（幂等，不覆盖用户手改）。提示用户人工确认。

## 📚 引用资源
- `playwright-generator-skill`：被审代码的生产方；需修复时回退修订。
- `playwright-healer-skill`：通过审核后的执行与自愈下游。
- `playwright-planner-skill` / `playwright-plan-review-skill`：提供审核依据 `business_flow.md`。
- `playwright-explorer-skill` / `playwright-explorer-review-skill`：上游事实与事实审核（本 Skill 不读取其原文裁定业务含义）。
