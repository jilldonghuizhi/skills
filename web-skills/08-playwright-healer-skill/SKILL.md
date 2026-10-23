---
name: playwright-healer-skill
description: 测试执行与自愈（playwright-pipeline-skill 阶段7）。在 PROJECT_DIR 下执行 pytest，失败时读失败日志与 PROJECT_DIR/e2e/traces/ 的 Playwright trace，诊断修复定位器/等待/断言，最多重试 MAX_HEAL_ATTEMPTS 次。是串联工作流的最后一步，也可独立使用。只修用例层；框架骨架问题交由 playwright-generator-skill 修复。
---

# Healer：测试执行与自愈（阶段7）

## 🎯 角色与目标

你是一位高级测试开发工程师，精通 Playwright 失败诊断与自愈（定位器/等待/断言/时序），负责把失败用例修复到稳定通过；只修用例层与页面对象，不动框架骨架。

**定位与上下游**：Playwright 用例生成链路的第 7 阶段（终点）：

**[playwright-explorer-skill 探索 → playwright-explorer-review-skill 审核 → playwright-planner-skill 梳理 → playwright-plan-review-skill 审核 → playwright-generator-skill 生成 → playwright-code-review-skill 代码审核] → 本 skill（执行 + 自愈）**

- **项目根**：`PROJECT_DIR`（流水线上下文或环境变量指定）；否则兼容 `E2E_ROOT`，再否则用 `PROJECT_NAME` 在当前目录确定项目根。相对路径均相对于该目录
- **上游**：通过代码审核的 `<PROJECT_DIR>/e2e/testcases/test_<feature>.py`
- **产出**：pytest 执行结果；报告由 `base_framework` 的 conftest 收尾自动生成（Allure + 邮件）
- **可独立使用**：对任意已存在的失败用例执行自愈修复，不必走完整链路

## 📋 前置条件与输入

### 1. 环境依赖
- Playwright 框架骨架已存在，且 `base_framework` 已 `pip install -e`
- Playwright 浏览器已安装（`playwright install`）
- 被审核通过的测试用例文件

### 2. 权限要求
- **只修用例层与页面对象**：不得修改框架骨架（`BasePage`/`browser_manager`/`conftest` 等）；骨架问题交由 `playwright-generator-skill` 处理。
- 任何来源的凭据均不得写入测试代码、配置文件、日志或报告。

### 3. 必填输入
- `PROJECT_DIR` 下通过代码审核的测试用例文件 `e2e/testcases/test_<feature>.py`。
- 失败时的 pytest 失败日志与 Playwright trace（`<PROJECT_DIR>/e2e/traces/`）。

### 4. 知识基线
- 诊断对照：生成侧权威规范见 `playwright-generator-skill` 的「等待与导航（硬性规范）」与「禁止猜测选择器清单」；Healer 据此定位失败根因并下沉修复，不另行重写该规范。
- 典型时序判例：JS 导航点击后 URL 不变、AJAX 异步文本读到空值、跨节点文本断言等。

## 🚶 标准化工作流

### Step 1：环境预检（确认项目根与前置条件）
- 确定 `PROJECT_DIR`（流水线上下文/环境变量，否则 `E2E_ROOT`，再否则 `PROJECT_NAME` 在当前目录确定）；相对路径均相对于该目录。
- 确认框架骨架存在、`base_framework` 已安装、浏览器已安装、待执行用例通过代码审核。

### Step 2：核心操作执行（执行 → 诊断 → 下沉修复）
测试失败时，读 pytest 失败日志 + Playwright trace（`<PROJECT_DIR>/e2e/traces/`），诊断并修复定位器/等待/断言，重试最多 `MAX_HEAL_ATTEMPTS` 次（默认 3）。

**修复范围**：
- 定位器失效 → 换语义化定位器或回退到更稳定的选择器
- 等待不足 → 补 `page.wait_for_*` 或 BasePage 的 `wait`
- 断言过严 → 调整断言文本/条件
- 时序问题 → 补显式等待
- **保持用例层零 Playwright API**：自愈修改同样不得在 `test_<功能>.py` 内直接写 `page.locator`/`get_by_`/`page.url` 等——新定位/断言/等待一律**下沉到对应页面对象方法**（如 `wait_for_xxx()`/`xxx_text()`/`expect_xxx()`），用例只调用方法；已存在用例内的原始 locator 可顺手下沉（保持规范），但不重构无关代码
- 典型时序判例（优先按此修）：
  - JS 导航（`javascript:` 伪协议 href、JS 函数 href、`location.reload()`）点击后 URL 不变 → 用 `expect_navigation` 包裹点击
  - `target="_blank"` 点击后 URL 不变 → 用 `context.expect_page()` 捕获新页并返回
  - AJAX 表格/异步文本读到 0 行或空值 → 先 `wait_for_xxx()` 再断言
  - 断言目标文本分布在兄弟节点 → 按共同父级容器整体断言

**不修复**：框架骨架问题（`ScopeMismatch` 等 fixture 作用域设计问题，正确修法是把被 session 级消费者请求的 fixture 提升为 session 级，不得在用例层绕过）——交由 `playwright-generator-skill` 的框架初始化模式处理。

### Step 3：结果格式化（重试循环与处置）
执行 pytest → 失败 → 读日志/trace → LLM 诊断 → 改 `.py` → 重跑（最多 N 次）→ 通过或人工介入。

**使用方式**：
- 串联调用：由 `playwright-pipeline-skill/scripts/run_full_pipeline.py` 自动调用本 skill 的 `scripts/run_healer.py`。
- 单独调用：在 `<PROJECT_DIR>` 下执行（或设 `PROJECT_DIR` 环境变量）：
  ```powershell
  python .trae/skills/web-skills/07-playwright-healer-skill/scripts/run_healer.py e2e/testcases/test_login.py [最大重试次数] [--user <账号>] [--pass <密码>] [额外 pytest 参数 ...]
  ```
  脚本负责调用 pytest（`--alluredir=allure-results`，cwd 为项目根）与重试循环；LLM 在失败时介入读日志/trace 修复用例代码。Allure 结果、失败日志与报告均留在该项目目录中。其余未知参数与 `--` 之后的参数原样透传给 pytest（如 `-k` / `-m`）。

## ⚠️ 约束与规范

### 1. 代码规范（下沉修复）
- 自愈修改保持「用例层零 Playwright API」；新定位/断言/等待一律下沉到对应页面对象方法，用例只调用方法。

### 2. 安全边界
- 不修框架骨架（`BasePage`/`browser_manager`/`conftest`）；骨架问题回 `playwright-generator-skill`。
- 凭据不落盘：凭据不写入测试代码、配置文件、日志或报告。

### 3. 性能约束（重试上限）
- 最多重试 `MAX_HEAL_ATTEMPTS` 次（默认 3）；达到上限仍失败则转人工介入，不无限重试。

### 4. 输出规范
- 输出每次诊断与修复说明、最终通过状态或人工介入请求；Allure 结果/失败日志/报告留在 `PROJECT_DIR`。

## ✅ 验证与自查

### 1. 功能校验
- pytest 最终通过或达重试上限转人工；每次修复后重跑验证。

### 2. 完整性校验
- 失败根因（定位器/等待/断言/时序）均被覆盖修复；未误改框架骨架。

### 3. 常见错误排查
- **Windows / PowerShell**：不支持 bash heredoc（`python - <<'PY'` 会报 "redirection operator" 语法错误）；需运行临时 Python 验证/诊断脚本时，先写入临时 `.py` 文件执行，结束后删除。
- **误导性 `unrecognized arguments`**：pytest 报 `unrecognized arguments: --xxx`（自定义选项）时，先确认目标测试文件/目录**真实存在**——目标不存在时 pytest 不加载其目录链上的 conftest，会报出与本因无关的 unrecognized；再检查项目 conftest 是否经 `pytest_addoption` 注册该选项（可用 `pytest --help` 验证）。
- **临时探针清理**：验证 fixture/凭据行为用的探针测试文件，验证完成后必须删除，并确认没有遗留（探针脚本 `finally` 删除的文件不要再手动执行）。
- 误把 `ScopeMismatch` 等骨架问题在用例层绕过，而非回 Generator 提升 fixture 作用域。

### 4. 最终确认
- 达到稳定通过或明确转人工；凭据未落盘；未误改骨架。

## 📚 引用资源
- `playwright-generator-skill`：框架初始化与「等待与导航」「禁止猜测选择器」权威规范；骨架问题回退。
- `playwright-code-review-skill`：上游代码审核门禁（本 Skill 接其通过产物）。
- `playwright-pipeline-skill/scripts/run_full_pipeline.py` 与 `scripts/run_healer.py`：串联/单独执行入口。
- `base_framework`：报告由 conftest 收尾自动生成（Allure + 邮件）。

## 凭据提供（不强制来源）

登录类用例所需的账号密码**只要提供即可**，按项目 fixture 支持的任一方式：

- **pytest 命令行选项**：`--user <账号> --password <密码>`（由项目 conftest 的 `pytest_addoption` 注册）
- **run_healer.py 快捷项**：`--user <账号> --pass <密码>`（脚本自动转为 pytest 的 `--user=` / `--password=`）
- **环境变量**：`NOVEL_USER` / `NOVEL_PASS`（或其他项目约定名，由项目 fixture 决定）

优先级：命令行 > 环境变量（以项目 fixture 实现为准）。任何来源的凭据均不得写入测试代码、配置文件、日志或报告。
