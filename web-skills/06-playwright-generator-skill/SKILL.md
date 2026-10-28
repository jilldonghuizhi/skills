---
name: playwright-generator-skill
description: Playwright Web/UI 自动化框架与 POM 用例统一生成器。POM 用例生成**只消费**符合格式的`<模块>.testcase.md`（一模块一文件，与 `test_<功能>.py` 一一对应），仅生成其中「确定性+READY」及用户明确确认的场景；框架初始化模式独立。支持幂等增量，不覆盖用户实现，不注入真实凭据。
---

# Playwright Web 框架与 POM 用例生成器

## 🎯 角色与目标

你是一位高级测试开发工程师，精通 Playwright + pytest 与 POM 设计模式，负责把审核通过的业务流程落地为可运行、可维护的页面对象与测试用例：定位与断言全部封装在页面对象，用例层零 Playwright API。

本 Skill 统一负责 Web 框架初始化与 POM 用例生成。按用户请求选择工作模式，不重复生成、不覆盖已有文件。

| 模式 | 触发意图 | 产出 |
| --- | --- | --- |
| 框架初始化 | 生成 Playwright/Web 自动化框架、pytest 骨架 | `config/`、`base/`、`common/`、`utils/`、`pages/`、`components/`、`tests/`、根 `conftest.py`/`pytest.ini`、CI/CD、README |
| POM 用例生成 | 按 `<模块>.testcase.md` 中「可生成场景」生成页面与用例 | `pages/`、`tests/` 的功能代码 |

**生成顺序（硬性）**：框架初始化先于用例生成。POM 用例生成依赖框架初始化产出的 `base/`、`common/`、`utils/`、`tests/conftest.py`、`config/` 等骨架，任一缺失时先补齐框架骨架再生成用例；用户仅要求其中一项时，不额外扩展另一项。

**总体原则（封装与复用，一切规则的总纲）**：
- **封装**：定位、等待、断言一律封装在页面对象（`BasePage` / 页面类 / 组件类）；用例层零原始 Playwright API，只调用页面对象方法与原生 `assert`。组件只被页面对象在内部消费，不暴露给测试文件。
- **复用优先（避免重复代码）**：跨页面 / 跨用例的共享逻辑与常量只写一处、下沉复用——通用操作进 `BasePage`，跨页公共元素进 `components/`，框架级共享常量进 `config/config.yaml`（可经环境变量覆盖），业务常量进 `common/constants.py`，共享 fixture 进 `tests/conftest.py`；严禁在多个页面类或用例文件间复制粘贴相同逻辑、相同硬编码常量与相同定位/等待片段。
- **单一职责**：一页一类（继承 `BasePage`）、一功能一类一文件、组件只供页面消费、框架级共享常量只进 `config.yaml`、业务常量只进 `constants.py`、共享 fixture 只进 `conftest.py`，互不越界。

**定位（POM 用例生成）**：
- 本 Skill 唯一业务输入为符合格式的 per-module `<PROJECT_DIR>/spec/<模块>.testcase.md`（消费规则见 Step 2）；不读取原始需求、聊天记录或实时页面来补充**场景/步骤/断言/数据**（定位器由本阶段经 Playwright MCP 真实页面实测获取，见 Step 2）。
- 可独立调用；输入不完整或不匹配时停止并交回 testcase 修订，不与代码审核职责混淆。

## 📋 前置条件与输入

### 1. 环境依赖
- 日志、YAML 配置读取、报告汇总、邮件发送与 Allure 报告生成等通用能力，由框架初始化生成的 `utils/` 包统一提供（`logger` / `config_reader` / `report` / `email_sender`）。
- 项目根目录由 `PROJECT_DIR` 指定；未设置时以当前工作目录为项目根。

### 2. 权限要求
- 不注入真实凭据：登录凭据（账号用户名与密码）来源为**用户指令或项目资料**（用户指令优先），运行期经 `tests/conftest.py` 的 `credentials` fixture（命令行 `--password` 或环境变量）注入，**不落盘**到仓库/截图/日志/代码。
- 已存在的 `<page>_page.py` / `test_<功能>.py` **默认不覆盖**，只补齐缺失方法/用例；用户手改内容原则上不覆盖，冲突时报告并交回裁决。

### 3. 必填输入
- POM 用例生成：`<PROJECT_DIR>/spec/<模块>.testcase.md` 应存在，且至少含「可生成场景」；若目标工程缺少 `base/base_page.py`、`tests/conftest.py` 或配置文件，先补齐缺失骨架再生成用例；确认 `utils/` 下 `logger`/`config_reader`/`report`/`email_sender` 已生成。
- 框架初始化：用户指定或运行环境提供的 `PROJECT_DIR`（未设置时单独使用本 Skill 才以当前工作目录为项目根）。

### 4. 知识基线
- POM 设计基础：一页一类、一功能一类一文件；定位/断言/等待封装在页面对象，用例层零原始 Playwright API。
- 稳定属性定位（首选 `id` 与 `data-test`/`data-testid`/`test-id` 契约级）、语义化 locator（次选 `name`/`role+name`/`link_text`）、结构层级定位（末选、默认禁用），以及真实页面实测采集（可见 HTML 抽取 / 受控 `evaluate` 只读探查）、等待导航区分、禁止猜测选择器等规范见 Step 2 与 `references/pom-generation.md`；定位器节流纪律见 `references/locator-budget.md`。

## 🚶 标准化工作流

### Step 1：框架初始化（`--init` 复制骨架）
运行以下命令从 `templates/` 复制框架骨架到 `PROJECT_DIR`（**幂等**：已存在文件保留，只生成缺失文件）：

```powershell
python scripts/run_generator.py --init [--base-url <url> --test-user <user> --browser-type chromium --headless true]
```

该命令生成以下文件与目录：
- `config/config.yaml`（渲染 4 个占位符：`__BASE_URL__`/`__TEST_USER__`/`__BROWSER_TYPE__`/`__HEADLESS__`，密码不落盘）
- `base/`（`__init__.py`、`base_page.py`）、`common/`（`__init__.py`、`browser_manager.py`、`constants.py`）
- `utils/`（`__init__.py`、`logger.py`、`config_reader.py`、`report.py`、`email_sender.py`）
- `tests/conftest.py`、根 `conftest.py`、`pytest.ini`、`requirements.txt`、`.github/workflows/ci.yml`、`README.md`、`.gitignore`
- 空目录 `pages/`、`components/`、`data/`、`spec/`（含 `pages/__init__.py`、`components/__init__.py`）

详细字段、pytest.ini、CI/CD、凭据注入、session 钩子等见 [`references/framework-init.md`](references/framework-init.md)。

### Step 2：POM 用例生成（消费 testcase.md）
1. 先运行 `python scripts/run_generator.py <模块>.testcase.md`（或仅传 feature 名自动 glob `spec/*.testcase.md`）校验输入并列出待生成功能；`--check-locators` 扫描 `pages/*.py` 的疑似未验证/多匹配选择器，`--audit-locators` 依据 `spec/evidence/locators-<页>.json` 审计采集是否满足"按步骤/不冗余/不猜测/稳定可靠/**档位未降级**(tier==max_tier)"五性质（含逐级提成降级检测）。
2. 加载 [`references/pom-generation.md`](references/pom-generation.md)，按其「强制三步生成顺序」生成 `pages/` 与 `tests/`：① 落页面类骨架 → ② 回填方法体（locator 由真实页面可见 HTML 抽取 / 受控 `evaluate` 只读探查实测，注释 `# 实测命中`）→ ③ 写测试用例。
3. 页面对象封装定位/等待/断言，用例层零原始 Playwright API；定位器强制实测与节流见 `references/locator-budget.md`。框架骨架已由 `--init` 生成，本阶段不再手写 `templates/` 中的模板文件。

### Step 3：结果格式化（使用方式 + 幂等约定 + 交付）
**使用方式**：
```powershell
# 指定某一模块（推荐，按 testcase.md 格式）：脚本校验该模块文件并列出待生成功能
python scripts/run_generator.py spec/<模块>.testcase.md
# 或只传 feature，脚本自动 glob 该 feature 下全部 *.testcase.md 模块文件
python scripts/run_generator.py web_frontend
```
脚本**只接受** testcase.md 模块文件；校验输入并列出模块后，由 LLM 按 `references/pom-generation.md` 三步流程实现代码（可选参考 `templates/` 的 `seed_page.py.template` / `seed_test.py.template` 结构），依据「可生成场景」。

**幂等约定**：
- 已存在的 `<page>_page.py` / `test_<功能>.py` **默认不覆盖**，只补齐缺失方法/用例；但 testcase.md 更新导致内容需变化时，可修改对应代码段。
- 用户手改内容原则上不覆盖；与 testcase.md 冲突时报告并交回裁决。
- **一页一类**：testcase.md 可生成场景新增页面时新建对应 `<page>_page.py`，不塞进既有类。
- **一功能一类一文件**：新增测试场景归入对应功能的 `test_<功能>.py` / `class TestXxx`；若该功能文件不存在则新建；**禁止**把新功能 class 塞进既有功能文件。
- **共享 fixture 集中管理**：跨功能共享的 fixture 统一落 `tests/conftest.py`，已存在时只补缺失、不覆盖。

**产出后**：进入 `playwright-code-review-skill` 代码审核门禁，**通过才可执行 pytest**。

## ⚠️ 约束与规范

### 1. 代码规范（封装 / 页面对象 / 用例 / 定位器）
- 封装、复用优先、单一职责三条总原则（见 🎯 总体原则）贯穿始终；定位/等待/断言全部封装在页面对象，用例层零原始 Playwright API。
- 语义化 locator、强制实测命中（`# 实测命中`）、等待导航区分、一页一类/一功能一类一文件等硬性规则详见 `references/pom-generation.md`。
- 参数化用例硬规则（详见 `references/pom-generation.md` 参数化小节）：testcase.md 标注 `[参数化]` 或含数据矩阵的场景，生成**必须**用 `@pytest.mark.parametrize` 将每行数据展开为独立测试节点；**严禁**在单个 `def test_*` 内用 `for row in test_data / _DATA / data[...]: ... assert` 遍历数据矩阵（该写法使所有数据行塌缩为一个节点，单行失败即整例失败，且无法单独报告、`--lf` 重跑、`-k` 选跑、Healer 自愈）。数据矩阵存放 `data/<module>.yaml`，并在**测试模块级**加载（parametrize 装饰器在收集期求值、不可引用 fixture 实例）。

### 2. 安全边界
- 凭据（用户名/密码）来自用户指令或项目资料（用户指令优先），仅用于 MCP 定位会话或经 `credentials` fixture 注入，**绝不写入**生成文件/conftest/日志/截图/代码。
- 用户已有实现默认保留，冲突时报告裁决。

### 3. 性能约束（幂等与三步门禁）
- 三步生成顺序不得跳步；每步自检（`py_compile` / `--check-locators` / `--check-parametrize` / `collect-only` / 零原始 Playwright API）失败就修到通过再下一步（详见 `references/pom-generation.md`）。
- 已存在文件默认不覆盖。

### 4. 输出规范（产出边界）
- 产出 = N 个页面对象文件 + M 个测试用例文件（一个业务模块一个文件，与 `<模块>.testcase.md` 一一对应）；按「可生成场景」生成，不得为填满覆盖面而实现未确认场景。
- 不生成非用户要求的框架/用例项；不引入 `pytest-html`（除非用户明确要求）。

## ✅ 验证与自查

### 1. 功能校验
- 框架初始化：`compileall -q .` 与 `pytest --collect-only -q` 通过；源码仅依赖本项目内模块（`base`/`common`/`utils`/`pages`/`components`/`tests`）与 `requirements.txt` 中声明的第三方包（详见 `references/framework-init.md` 初始化验证）。
- 三步生成每步自检通过：骨架 `py_compile` → 页面对象 `py_compile` + `--check-locators` 零疑似 → 用例 `py_compile` + `collect-only` + `--check-parametrize` 零伪参数化 + 用例文件零原始 Playwright API。

### 2. 完整性校验
- 每个 `确定性 + READY` 场景均生成对应测试方法与页面对象方法；`NEEDS_CONFIRMATION`/`BLOCKED`/探索性场景仅在用户确认生成时才生成可运行用例，未获确认时不生成（不视为遗漏）。
- 共享 fixture 集中于 `tests/conftest.py`，未在各用例文件重复定义；框架级共享常量集中于 `config.yaml`、业务常量集中于 `common/constants.py`，未在各用例文件硬编码。

### 3. 最终确认
- 三步自检全过；`--check-locators` 零疑似；`--check-parametrize` 零伪参数化；产出进入 `playwright-code-review-skill` 门禁（通过才可执行 pytest）；未经用户确认的 `NEEDS_CONFIRMATION`/`BLOCKED`/探索性 场景未提前生成。

## 📚 引用资源
- `references/framework-init.md`：框架初始化详细附录（`config/web` 字段、pytest.ini、CI/CD、凭据注入、session 钩子）；仅框架初始化模式加载。
- `references/pom-generation.md`：POM 用例生成详细附录（页面对象/测试用例规则、定位器规范、三步顺序、参数化）；仅 POM 用例生成模式加载。
- `references/locator-budget.md`：locator 实测节流附录（工具白名单、单页 1 快照预算、去重指纹、上下文收口、入口发现兜底）；POM 生成阶段加载。
- `scripts/run_generator.py`：执行入口（`--init` 复制框架骨架；`--check-locators` 扫描疑似未验证定位器；`--check-parametrize` 拦截 for 循环代替 `@pytest.mark.parametrize` 的伪参数化；校验 testcase.md 输入）。
- `playwright-testcase-skill`：本 Skill 唯一业务输入来源（消费其 per-module `<模块>.testcase.md`）；输入不完整或不匹配时回流交由其修订，不回溯 planner skill。
- `playwright-code-review-skill`：后续代码审核门禁（本 Skill 产出后进入）。
- `playwright-healer-skill`：审核通过后执行与自愈后续。
