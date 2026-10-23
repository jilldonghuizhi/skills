---
name: playwright-generator-skill
description: Playwright Web/UI 自动化框架与 POM 用例统一生成器。POM 用例生成**只消费**符合格式的`<模块>.testcase.md`（一模块一文件，与 `test_<功能>.py` 一一对应），仅生成其中「确定性 + READY」场景；框架初始化模式独立。支持幂等增量，不覆盖用户实现，不注入真实凭据。完整流水线执行由 playwright-pipeline-skill 编排。
---

# Playwright Web 框架与 POM 用例生成器

## 🎯 角色与目标

你是一位高级测试开发工程师，精通 Playwright + pytest 与 POM 设计模式，负责把审核通过的业务流程落地为可运行、可维护的页面对象与测试用例：定位与断言全部封装在页面对象，用例层零 Playwright API。

本 Skill 统一负责 Web 框架初始化与 POM 用例生成。按用户请求选择工作模式，不重复生成、不覆盖已有文件。

| 模式 | 触发意图 | 产出 |
| --- | --- | --- |
| 框架初始化 | 生成 Playwright/Web 自动化框架、pytest 骨架 | `config/`、`e2e/web/`、通用 fixtures、配置、运行入口、README |
| POM 用例生成 | 只按符合格式的 `<模块>.testcase.md` 中「确定性 + READY」场景生成页面与用例 | `e2e/pages/`、`e2e/testcases/` 的功能代码 |
| 完整流水线 | 探索 → Explorer Review → Planner → Plan Review → 生成、代码审核、执行和自愈 | 由 `playwright-pipeline-skill` 编排本 Skill 与其他阶段 |

请求同时要求框架和业务用例时，先生成或补齐框架，再生成用例；用户只要求其中一项时，不额外扩展另一项。

**总体原则（封装与复用，一切规则的总纲）**：
- **封装**：定位、等待、断言一律封装在页面对象（`BasePage` / 页面类 / 组件类）；用例层零原始 Playwright API，只调用页面对象方法与原生 `assert`。组件只被页面对象在内部消费，不暴露给测试文件。
- **复用优先（避免重复代码）**：跨页面 / 跨用例的共享逻辑与常量只写一处、下沉复用——通用操作进 `BasePage`，跨页公共元素进 `e2e/components/`，框架级共享常量进 `config/config.yaml`（可经环境变量覆盖），业务常量进 `e2e/web/constants.py`，共享 fixture 进 `e2e/testcases/conftest.py`；严禁在多个页面类或用例文件间复制粘贴相同逻辑、相同硬编码常量与相同定位/等待片段。
- **单一职责**：一页一类（继承 `BasePage`）、一功能一类一文件、组件只供页面消费、框架级共享常量只进 `config.yaml`、业务常量只进 `constants.py`、共享 fixture 只进 `conftest.py`，互不越界。

**定位与上下游（POM 用例生成）**：

**[playwright-explorer-skill 探索 → playwright-explorer-review-skill 审核/事实补测] → [playwright-planner-skill 输出业务流程与 READY 场景 → playwright-plan-review-skill 审核/修订] → [playwright-testcase-skill 把 READY 场景按业务模块拆为 per-module `<模块>.testcase.md`] → 本 Skill **只消费** testcase.md 生成页面与用例 → [playwright-code-review-skill 代码审核] → [playwright-healer-skill 执行自愈]**

- POM 生成唯一业务输入为符合格式的 per-module `<PROJECT_DIR>/spec/<模块>.testcase.md`（含 `确定性+READY` 场景）。Generator 不读取原始需求、聊天记录或实时页面来补充场景、步骤、断言、定位器和数据；这些事实必须由 testcase.md 交接。
- 可独立调用，只需提供符合格式且含 `确定性+READY` 场景的 `<模块>.testcase.md`；不得以用户直接提供的需求或口头补充替代该输入。若 testcase.md 不完整或不匹配，停止并交回修订。
- 不在代码生成阶段代替探索记录/代码审核 Gate；完整流程由 `playwright-pipeline-skill` 负责。

## 📋 前置条件与输入

### 1. 环境依赖
- Web 框架复用 `python-pytest-base-framework` 提供的外部 `base_framework` 包；先用 `pip install -e <base_framework路径>` 安装，并验证 `import base_framework`。不复制或修改底座包，也不触发底座 Skill。
- 运行命令的工作目录、`PROJECT_DIR` 和 `E2E_ROOT` 必须指向同一个项目根目录。`PROJECT_DIR` 优先；`E2E_ROOT` 仅为旧调用兼容；两者未设置时可用 `PROJECT_NAME` 在当前目录解析项目根。计划、探索记录放 `PROJECT_DIR/spec/`，代码和运行件放 `PROJECT_DIR/e2e/` 与项目根。
- Web 层只负责 Playwright 浏览器生命周期、页面对象、Web fixtures、UI 用例与截图/trace 采集；日志、YAML 配置读取、报告汇总、邮件和 Allure 报告生成均调用 `base_framework`。
- 生成 CI/CD 文件，不引入 `pytest-html`，除非用户明确提出额外需求。

### 2. 权限要求
- 不注入真实凭据：登录凭据（账号用户名与密码）来源为**用户指令或项目资料**（用户指令优先），运行期经 `e2e/testcases/conftest.py` 的 `credentials` fixture（命令行 `--password` 或环境变量）注入，**不落盘**到仓库/截图/日志/代码。
- 已存在的 `<page>_page.py` / `test_<功能>.py` **默认不覆盖**，只补齐缺失方法/用例；用户手改内容原则上不覆盖，冲突时报告并交回裁决。不复制底座包、不触发底座 Skill。

### 3. 必填输入
- POM 用例生成：`<PROJECT_DIR>/spec/<模块>.testcase.md` 应存在，且其确定性+READY；若目标工程缺少 `e2e/web/base_page.py`、`e2e/testcases/conftest.py` 或配置文件，先补齐缺失骨架再生成用例；安装并验证 `base_framework` 可导入。
- 框架初始化：用户指定或由流水线传入的 `PROJECT_DIR`（未设置时单独使用本 Skill 才以当前工作目录为项目根）。

### 4. 知识基线
- POM 设计：一页一类、一功能一类一文件；定位/断言/等待封装在页面对象，用例层零原始 Playwright API。
- 定位器语义化（`get_by_role`/`get_by_label`/`get_by_placeholder`/`get_by_test_id`），少用脆弱 CSS/XPath。
- 定位器实测取数方式：**只用 accessibility 语义快照（Playwright MCP `snapshot`）** 抽取 `role/name/text/placeholder` → 直接映射为语义化 locator；**禁用 `evaluate` / `get_page_source` 原始 DOM 工具**（规避脆弱 CSS/XPath）。节流纪律见 `references/locator-budget.md`。
- 等待与导航：异步渲染内容不得裸断言；严格区分真实导航（`expect_navigation`）与原地 JS 刷新/分页/筛选重渲染（不包 `expect_navigation`）；`target="_blank"` 用 `context.expect_page()` 捕获新页。
- 禁止猜测选择器清单：分页/页码、结果/列表容器、详情/字段容器、弹层/对话框、总页数/当前页文本等极容易猜错，必须实测命中。

## 🚶 标准化工作流

### Step 1：环境预检（框架初始化模式 + 文件布局 + 验证）
**依赖与责任边界**：见 📋 环境依赖。Web 层只负责浏览器生命周期/页面对象/Web fixtures/UI 用例与截图 trace 采集；其余调用 `base_framework`。

**初始化文件布局**（以 `PROJECT_DIR` 为唯一目标项目根；只生成缺少的文件，保留已有项目结构）：

```text
<PROJECT_DIR>/
├── spec/
│   └── <模块>.testcase.md   # generator 唯一业务输入（符合 testcase.md 格式）
├── config/config.yaml
├── data/                      # 测试数据（参数化用例数据源：YAML/JSON/CSV）
├── conftest.py
├── pytest.ini
├── requirements.txt
├── runner.py                 # 可选入口
├── README.md
└── e2e/
    ├── web/
    │   ├── browser_manager.py
    │   ├── base_page.py
    │   └── constants.py          # 业务相关常量（页面/功能语义化常量，非框架通用值）
    ├── pages/
    ├── components/
    └── testcases/
        └── conftest.py
```

**初始化约定**：
- `requirements.txt` 声明 pytest、pytest-xdist、allure-pytest、PyYAML、python-dotenv、Playwright，并引用外部 `base_framework`；安装浏览器使用 `python -m playwright install chromium`（或用户选择的浏览器）。
- `config/config.yaml` 包含 `web`、`report`、`email` 配置（可选 `auth.test_user` 仅存账号用户名）。`web` 段承载**框架级共享常量**（与具体业务/数据无关的通用值，可经环境变量覆盖）：如 `base_url`、`browser_type`、`headless`、`trace_enabled`、`default_timeout`、`network_idle_timeout`、`retry_count`、通用等待状态名、固定日志/断言文案等——这些值**不再硬编码在 `e2e/web/constants.py`**，改由 `ConfigReader` 读取。默认 `report.auto_open: false`、`email.enabled: false`；SMTP 密码、**测试账号密码**等敏感值只经环境变量/命令行注入，**不写入本文件**。

  `web` 段示例（框架级共享常量，模板层给通用默认值，生成时按项目资料覆盖）：

  ```yaml
  web:
    base_url: ''
    browser_type: 'chromium'
    headless: true
    trace_enabled: true
    default_timeout: 30000        # 元素操作默认超时（毫秒）
    network_idle_timeout: 5000    # 网络空闲等待（毫秒）
    retry_count: 2                # 失败重试次数
    wait_states:                  # 通用等待状态名（Playwright 状态）
      - 'load'
      - 'domcontentloaded'
      - 'networkidle'
  ```
- **配置渲染（占位符替换，密码不落盘）**：框架初始化模式生成 `config/config.yaml` 时以 `templates/config.yaml.template` 为蓝本。模板层只保留通用占位符（`__BASE_URL__`、`__TEST_USER__`、`__BROWSER_TYPE__`、`__HEADLESS__`），**绝不写死任何项目的真实地址、账号或资料文件名**。生成 `config/config.yaml` 时，才从项目资料读取真实 `BASE_URL` 与测试账号**用户名**替换对应占位符；**密码（`__TEST_PASS__`）不替换**——任何生成文件、日志、截图、代码中均不写入明文密码。账号用户名（非密码）可随项目资料填入 `auth.test_user`，密码始终留空待注入。
- `pytest.ini` 默认内容（生成时直接写入，确保中文/特殊字符用例 ID 原样保留）：

  ```ini
  [pytest]
  testpaths = e2e/testcases
  markers =
      ui: Web UI 用例
      smoke: 冒烟用例
  disable_test_id_escaping_and_forfeit_all_rights_to_community_support = True
  ```

  该属性关闭 pytest 默认的用例 ID 转义，避免中文用例名（如 `test_login[登录成功]`）被转成不可读编码；注册 `ui`/`smoke` 等标记以避免 PytestUnknownMarkWarning。
- `data/` 存放测试数据（参数化用例的数据源，YAML/JSON/CSV）。每个功能模块对应一个 `data/<module>.yaml`（`<module>` 为测试模块名，如 `test_login.py` → `data/test_login.yaml`，与 `test_<功能>.py` 同名），由框架初始化生成的项目根 `conftest.py` 的 `test_data` fixture 按调用测试模块名自动加载（实现见 `conftest.py.template`）；框架初始化创建 `data/` 空目录（不预建示例数据文件），不在用例文件内硬编码大段输入数据。
- `BrowserManager` 负责 Playwright/browser/context 生命周期；`viewport` 配置在 `browser.new_context()`；浏览器类型/无头模式**只由 `config.yaml` 的 `web.browser_type` / `web.headless` 驱动**（要变更改配置或配置 profile）。**严禁注册 `--browser`/`--headed`/`--headless` 等 pytest 选项、也不得依赖 `WEB_BROWSER_TYPE`/`WEB_HEADLESS` 环境变量**——运行环境常已安装 `pytest-playwright` 等插件并注册了同名选项，重复 `addoption` 会触发 `option already added` 导致 pytest 启动即失败。按 `web.trace_enabled` 启动 trace，失败时导出到 `e2e/traces/`。**`e2e/screenshots/` 与 `e2e/traces/` 不预建空目录**：截图与 trace 落地前由对应代码 `Path(...).mkdir(parents=True, exist_ok=True)` 按需创建（框架初始化不生成 `.gitkeep`）。
- `BasePage` 包装导航、点击、输入、读取、断言和截图等常用操作，使用日志和 `allure.step`；页面对象继承 `e2e.web.base_page.BasePage`。导航统一调用基类 `goto()`（基于类级 `URL_PATH`：无参走 `URL_PATH`、传 `path` 覆盖）；**禁止生成 `open()` 调用**——框架 `BasePage` 不提供 `open()`，调用会在运行时抛 `AttributeError`，测试模板与页面对象均改用 `goto()`。
- `e2e/web/constants.py` 集中定义**业务相关常量**（与具体业务/页面语义强相关的常量）：如业务状态码、业务文案/枚举、页面固定业务标识、业务阈值等；**框架级共享常量（超时、等待状态、重试次数、通用日志/断言文案等）一律进 `config/config.yaml` 的 `web` 段，经环境变量覆盖，禁止在 constants.py 硬编码**。页面对象与用例统一 `from e2e.web.constants import ...` 引用业务常量，**禁止在页面对象或用例中硬编码这些业务常量**；框架级通用值由 `ConfigReader` 从 `config.yaml` 读取；仅单功能使用、与业务数据强相关的常量可放功能文件顶部或 `data/`，真正跨模块共享的业务常量才进 `constants.py`。
- 测试 `conftest.py` 提供 browser/context/page fixtures；失败截图 hook 只处理 call 阶段的 failed/broken 报告，显式导入 `Path`，并将截图附加到 Allure。trace 由 `BrowserManager.export_trace()` 导出后使用底座 `attach_failure_artifact("trace", trace_path)` 挂载；采集或挂载失败不得掩盖测试原始结果。
- **fixture 作用域约束（防 ScopeMismatch）**：被 session 级消费者请求的 fixture 必须声明 `scope="session"`（至少不低于消费者）。已知冲突：`pytest-base-url` 插件的 session 级 `_verify_url` 会请求 `base_url`——`base_url` 若为 function 级将报 `ScopeMismatch`。`base_url` 等包装 session 级资源（如 browser_manager）的 fixture 一并声明 session 级。
- **凭据注入（来源：用户指令或项目资料）**：登录凭据的来源优先级为「用户指令显式给出 > 项目资料（`auth` 段）」，任一提供即可。`e2e/testcases/conftest.py` 注册 `pytest_addoption`（`--user` / `--password`，可带 `--pass` 别名）；`credentials` fixture 取值优先级为「命令行 > 环境变量（项目约定名如 `WEB_USER`/`WEB_PASS`）」，任一来源提供即可（凭据实际值同源用户指令或项目资料，但**不写入** `e2e/` 下任何文件与日志）；均未提供时用占位值让登录用例自然失败。生成阶段若需 MCP 登录以采集需鉴权页面的 locator，同样取该凭据用于本次 MCP 会话，用完即弃、不落盘。
- `pytest_sessionstart` 调用 `reset_allure_dir("allure-results")`，只传目录参数；`pytest_sessionfinish` 调用 `finalize_report_session(session, env=..., auto_open=..., email_enabled=...)`，显式传入配置开关。以底座现有并行安全逻辑收尾，不自行重复生成报告或发邮件；邮件默认关闭。
- `BrowserManager` 记录浏览器 brand/version/headless 信息供报告环境信息使用。并行执行时每个 xdist worker 独立创建浏览器资源，fixture teardown 必须释放资源。
- `runner.py` 提供 `--base_url`、`--workers/-n`、`--tests` 等参数；**不得注册 `--browser`/`--headed`/`--headless`**（浏览器类型/无头模式由 `config.yaml` 的 `web.browser_type`/`web.headless` 驱动）；不得把口令写入文件或日志。
- `e2e/testcases/` 在框架初始化时为空目录，不预置示例用例文件；首个功能用例由 POM 生成阶段按 `<模块>.testcase.md` 创建 `test_<功能>.py` 写入。若需验证失败截图/trace 挂载，提供显式 opt-in 的本地失败用例；**不可让默认 pytest 测试套件故意失败**（默认空套件天然跳过，不访问外网）。
- `e2e/pages/` 与 `e2e/components/` 在框架初始化时为空目录，不预置占位示例；进入 POM 生成模式后按 testcase.md 页面对应创建 `<page>_page.py`（与 testcase.md 中交接的页面一一对应），跨页公共组件类（如 `Header`/`CommonLayer`）则写入 `e2e/components/<name>.py`；避免代码审核门禁将无关文件判为清单外残留。

**初始化验证**：在目标项目根目录安装依赖及底座包、安装选用的 Playwright 浏览器，然后运行：
```powershell
python -m compileall -q e2e conftest.py
python -m pytest --collect-only -q
```
若生成 `runner.py`，另行对其运行 `py_compile`。报告检查以机器可读的 `report.json` 和 Allure 结果文件为准；不安装 Allure CLI 时不宣称已生成 HTML 报告。不得发送真实邮件或访问真实账号来证明骨架可运行。

### Step 2：核心操作执行（POM 用例生成 — 消费 testcase.md + 页面对象 + 测试用例 + 三步顺序）
**输入：消费 testcase.md**（唯一业务规格）：符合格式的 per-module `<PROJECT_DIR>/spec/<模块>.testcase.md`，仅含纯测试用例（字段：用例编号、所属模块、用例标题、优先级、前置条件、测试步骤、预期结果、测试数据、就绪状态，零证据）。Generator 按模块读取对应文件，**仅消费其中标注 `确定性 + READY` 的场景**；定位线索（选择器）由 Generator 在真实页面经 accessibility 语义快照实测获取，不来自 testcase.md。

生成前必做：用 Glob 扫描 `spec/*.testcase.md`（排除 `explorer.md`），列出本 feature 的全部模块文件；每个文件对应一个待生成功能模块。无 testcase 文件时停止并报告。

读取与实现遵守以下规则：
1. testcase.md 是唯一业务规格；仅实现其中明确标注 `确定性 + READY` 的场景。`NEEDS_CONFIRMATION` / `BLOCKED` / 探索性场景（含「保留」小节）不得生成可运行用例，也不得自行提升状态。
2. 页面、动作、步骤顺序、角色、测试数据、断言谓词/预期值及清理边界，必须已在对应 READY 场景中提供；**定位线索不来自 testcase.md**（上游不提供），由本阶段在真实页面用 Playwright MCP 的 accessibility 语义快照实测获取（按本 Skill「定位器来源与强制验证」的两阶段法）。缺少任何生成必需信息（除定位线索外）时停止该场景并交回 testcase 修订，不得从其他来源推断或补写。
3. 保留并**透传** testcase.md 给出的**用例 ID（`<模块名>-<实际业务名>`，如 `登录认证-登入成功`）、优先级、就绪状态**作为追溯元数据；生成的每个 `test_` 方法必须以该用例 ID 显式标注，确保代码与 `<模块>.testcase.md` 一一对应、可反向追溯。testcase.md 不含证据线索（REC/§/测试点），如需追溯证据见独立的 `testcase-evidence.md`，Generator 不依赖该文件。testcase.md 内部有缺漏、冲突时，交回 testcase 修订。
4. 不从 testcase.md 之外自行扩展场景；只有 testcase.md 明确列为 `确定性 + READY` 的场景可生成。
5. 不新增 testcase.md 未提供的 selector、断言文案、数据值、角色、状态转换或业务步骤。代码语法、POM 结构及 locator 实现方式可按本 Skill 和现有框架约定完成，但不得改变业务含义。
6. READY 条目不保证 locator、fixture、环境或用例可运行。按代码审核及 `pytest --collect-only` 门禁验证；实际页面运行只能在后续明确授权的执行阶段进行。

**1. 页面对象 `e2e/pages/<page>_page.py`（一页一类，按 READY 场景中交接的页面拆分）**：
- **拆分依据**：testcase.md 确定性+READY 场景中交接的页面及路径；每个页面对应一个独立文件。Generator 不打开 REC 源文件。例：`HomePage` → `e2e/pages/home_page.py`。跨页公共元素（header 搜索、导航、公共弹层等）归 `e2e/components/` 下的组件类单独成文件，由相关页面对象在内部组合/继承消费，测试文件不直接引用组件类；组件类同样继承 `BasePage`，不混入具体页面业务逻辑。**禁止**把多个页面塞进一个 `page.py`。
- 每个类 `class <PageName>(BasePage)`，继承框架初始化生成的 `BasePage`，`from e2e.web.base_page import BasePage`。
- 定位器**语义化**：`page.get_by_role / get_by_label / get_by_placeholder / get_by_test_id`，少用脆弱 CSS/XPath。
- **禁用会命中多节点的属性/结构选择器（strict mode 多匹配违规根因）**：`a[href=...]`、后代 `x a`、`a:has-text(...)`、`tag.class` 等按属性/类/文案模糊匹配的选择器极易一对多——同一目标 URL 常同时存在「页头文字链 + CTA 按钮」等多个节点（如 `/user/register.html` 命中「注册」与「立即注册」）。当 accessibility 快照中出现「同 href / 同 class 的多个节点」，必须改用 `get_by_role("link"/"button", name=<可见文案>, exact=True)` 或 `get_by_text(<文案>)` 按**可见文案唯一区分**，不得用共享属性选择器。
- **定位器来源与强制验证（杜绝猜测，硬性规则）**：真实页面上**精确 locator 的实测采集是本阶段的唯一职责与硬性环节**（上游均不提供任何定位线索）。本阶段采集严格遵循 `references/locator-budget.md`，**只用 accessibility 语义快照（`snapshot`）** 替代原始 DOM 读取：快照树给出的 `role / name / text / placeholder` 直接映射为 generator 偏好的语义化 locator（`get_by_role`/`get_by_label`/`get_by_placeholder`/`get_by_text`），**禁用 `evaluate` / `get_page_source` 等原始 DOM 工具**（规避脆弱 CSS/XPath）。每个 locator 在快照中确认命中（`count()>0` 或可见）后提取语义选择器写入，注释 `# 实测命中：<选择器说明>`（如 `# 实测命中：分页组件末页链接`）。testcase.md **不含定位线索字段**，不得从其臆造或"原样沿用"选择器；上游任何阶段都未提供选择器，故本阶段必须实测。

  **采集两阶段（先静态圈定，再按页单快照实测，最少操作）**：
  - **阶段 0 · 静态推导「必要 locator 集合」（零 MCP）**：遍历本模块全部 `确定性+READY` 场景，**只从「测试步骤」与「预期结果/断言」解析**所需控件与断言锚点——`点击X`→X 的定位、`fill Y`→Y、`select Z`→Z；断言中的结果集→结果容器、计数/页数→计数/分页元素、状态/错误文案→文本锚点、空态→空结果区。合并去重为 `locator 需求表：{页面/状态, 控件语义名, 用途(动作/断言), 来源场景}`。**凡 testcase 未提及的元素一律不采集**；结构型容器（结果/分页/空态）仅在断言明确需要时才列入，不臆造。此表不开浏览器即定死采集范围，是降本核心。
  - **阶段 1 · 按页/状态分组 + 单快照实测 + 去重指纹**：把需求表按「页面/状态」聚类，导航次数 ≈ **不同页面/状态数**（而非场景数×控件数）。每页/状态**仅一次 `navigate` + 一次 accessibility 快照**，从该快照一次性抽取该页全部所需语义 locator（控件 + 断言容器同页免费可得）；同页跨场景/跨页面类**复用同一次快照与 locator**（去重指纹 = `URL + 角色态`，指纹不变则引用已采集结果，不重复导航/快照）。登录态页面（书架/个人中心/充值/阅读等）共用一次 `logged_in_page` 登录会话；能用稳定 URL 直达的（如 `/login`、列表页）直接 `navigate`，不层层点击进入。原始快照**落盘为 `spec/evidence/locators-<页>.json`**，上下文只保留 `页面 → [语义locator]` 清单，不滞留原始快照（上下文收口）。
  - **阶段 1 唯一性硬门禁（杜绝多匹配）**：每个 locator 在写入前，**必须**在对应页用 Playwright MCP 实测 `locator.count() == 1`（或首节点可见）；`count() > 1` 即为「多匹配违规」，须精炼到唯一（按可见文案 `name` / `get_by_text` 区分，或加父容器层级限定）后再写；`count() == 0` 为「未命中违规」，须回快照重查节点。已确认唯一的 locator 在注释补 `# 唯一` 标识（供 `--check-locators` 放行，否则按多匹配风险判错）。
  - **阶段 2 · 入口发现兜底（仅触发条件启用）**：纯图标按钮、隐藏文本、仅有 placeholder 的输入框在语义树不可见时，用**最小交互探测**（hover/点击暴露）或区域截图兜底确认存在后再取 locator；仅在触发条件启用，**不每页盲做**，避免额外操作。

  **实测前置与硬门禁（不变）**：
  1. **步骤/断言描述定位**：优先依据阶段 0 `locator 需求表` 在对应页快照实测定位并命中。
  2. **结构型/必需但未描述的元素**：结果容器、分页、当前页、空结果区、计数容器、弹层等"结构型"定位器，按阶段 0 需求表（断言需要才列入）在对应页快照查证节点并提取，注释 `# 实测命中`。
  3. **实测前置条件：BASE_URL 与登录凭据来自用户指令或项目资料**：MCP 实测需要可访问的真实页面。生成前取得 `BASE_URL` 与**登录账号的用户名及密码**——优先采用用户指令显式给出的，否则从项目资料读取；需登录才能访问的页面，本阶段用该凭据在 MCP 会话内登录后再采集其 locator（复用 `logged_in_page` 会话）。凭据仅用于本次 MCP 定位会话，**绝不写入任何生成文件、conftest、日志或截图**；运行期仍由 `credentials` fixture 经环境变量/命令行注入。
  4. **必须产出真实 locator，禁止占位、禁止推迟到自愈阶段**：本阶段对 testcase.md 中**每个** `确定性+READY` 场景涉及的页面，都必须完成快照实测并写入真实选择器（注释 `# 实测命中`）。**不得**生成 `TODO_VERIFY` 占位符，**不得**把 locator 采集推迟到 code-review / Healer 阶段。若用户指令与项目资料均缺少 `BASE_URL` 或某场景所需登录凭据，导致无法 MCP 访问对应页面，则**停止该场景并报告缺什么**（交回用户/testcase 补齐），不以猜测值或占位符蒙混，也不留待后续自愈补测。
- 业务方法封装原子操作，内部调 `self.click/fill/get_text`（继承自 BasePage，自带日志与 `allure.step`）。
- **定位与断言全部封装在页面对象（用例层零 Playwright API）**：
  - locator（`page.locator`/`get_by_role`/`get_by_text` 等）**只允许出现在页面对象方法内**；测试用例文件内禁止任何原始定位 API。
  - 页面对象提供**状态读取方法**：`xxx_text() -> str` / `xxx_count() -> int` / `is_xxx() -> bool`，返回纯 Python 值供用例 `assert`，读取前内部必须完成等待。
  - 或提供**断言封装方法**：`expect_xxx(...)`，内部用 `playwright.sync_api.expect`（自带自动重试等待），用例直接调用。
  - URL/title 断言同样封装为页面对象方法（如 `current_url()`），用例不直接访问 `page.url`/`page.title()`。
- **等待与导航（硬性规范）**：
  - **页面打开只用基类 `goto()`（基于 `URL_PATH`），禁止 `open()`**：框架 `BasePage` 仅提供 `goto()`，未定义 `open()`；生成代码若调用 `open()` 会在运行时抛 `AttributeError`。测试模板（`seed_test.py.template`）与页面模板（`seed_page.py.template`）均已统一为 `goto()`；无参 `goto()` 走类级 `URL_PATH`，传 `path` 可覆盖。
  - **异步渲染内容不得裸断言（load 事件不等于数据就绪）**：AJAX 表格/列表/延迟加载文本在 `count()`/`inner_text()` 前必须先等待。仅依赖 `expect_navigation`/`load` 不够——`load` 返回时 AJAX 数据往往还没渲染。页面对象触发 AJAX 后必须显式等待：优先 `self.page.wait_for_load_state("networkidle")`，或 `locator.wait_for()` / `nth(n).wait_for()`；提供 `wait_for_xxx()` 方法封装，用例断言前调用。
  - **严格区分「真实导航」与「原地 JS 刷新/分页」，二者等待方式不同**：真实导航才用 `expect_navigation` 包裹点击（链接 `href` 指向真实 URL、`location.href` 赋值、表单 `action` 提交、`location.reload()`）；不确定时方法提供 `wait_for_navigation: bool = False` 参数。原地 JS 刷新 / 分页 / 筛选重渲染（`href="javascript:;"`、AJAX 列表、组件库分页、`search()` 类 JS 函数）**绝不**包 `expect_navigation`——这类点击不触发 Playwright 导航事件，包裹会直接超时失败；正确做法：点击后 `wait_for_load_state("networkidle")` 或等目标元素重渲染。分页/筛选/搜索类方法默认**不**带 `wait_for_navigation`，并在 docstring 标注「JS 原地更新」。
  - **`target="_blank"` 链接用 `context.expect_page()` 捕获新页**：方法提供 `new_tab: bool = False` 参数，捕获 popup 并 `wait_for_load_state()` 后**返回新 page**；用例对返回的新 page 构造对应页面对象再断言（页面对象构造函数须支持传入任意 page 实例）。
  - **断言按真实 DOM 层级取容器**：目标文本分布在兄弟节点时（如 `<i>标签：</i><em id="value">内容</em>单位`）按共同父级整体定位断言，不得假设文本集中在单一元素。
  - **计数类断言要剔除表头/非数据行**：列表 `tbody#resultList tr`（表头在 `thead`，不计入）vs 裸 `table tr`（会把表头算成 1 行导致「0 结果」误判为有结果）。结果容器选择器必须经过实测，不得用含糊的 `table tr` 做计数。
  - **避免依赖站点数据分布的"值变化"断言**：不用"筛选后首行书名应变化"这类受数据波动影响的断言；优先状态类断言（选中态 class、存在性、计数 ≥1）。具体数字/页数断言仅在 testcase.md 明确给定且该值稳定时才用，否则改为「总页数可解析为数字且 ≥1」这类稳定断言。
- **禁止猜测选择器清单（Generator 头号错误源，硬性约束）**：以下类别的选择器**极容易凭常见命名猜错**，必须全部经 Playwright MCP 的 accessibility 语义快照实测命中（注释 `# 实测命中：…`），**不允许** `TODO_VERIFY` 占位或推迟到自愈阶段：
  - **分页/页码**：`#pages`、`.current`、`.active`、按文本 `a:has-text("下一页")` 等常见猜测都不可信；真实结构常为组件库分页链接（如 `a.<lib>-next`），必须实测。
  - **结果/列表容器**：业务自定义 id（如 `#resultList`）与裸 `table tr` 等含糊写法；必须实测确认容器 id / 数据行是否含表头。
  - **详情/字段容器**：业务自定义 id（如 `#detailPanel`）等整块容器；字段取值应定位到具体节点（如 `td.name a`），不得假设整块文本。
  - **弹层/对话框**：组件库自定义类（如 `.modal`），需实测确认具体类名。
  - **「总页数/当前页」文本**：不得假设出现在某固定元素；应实测定位（不同组件库取总页数方式不同）。
  - 识别信号：任何**未标 `# 实测命中`、又非 `get_by_role`/`get_by_label`/`get_by_placeholder` 等语义化定位**的 CSS id/class 选择器，若属于上述类别，即为「疑似未验证猜测」。`run_generator.py --check-locators` 会扫描 `e2e/pages/*.py`，将未实测的疑似项（含 `TODO_VERIFY` 占位）**视为错误**报告，必须由本阶段补 MCP 实测消除，不得放行到后续阶段。`--check-locators` 另扫描「疑似多匹配选择器」（`a[href=...]`、`:has-text(`、后代 `] a` 等）：即使已标 `# 实测命中`（只证明存在、不证明唯一），只要未显式标 `# 唯一`（采集期已用 `count()==1` 验证）即判为错误，须改用语义按名定位或补 `# 唯一` 标注。
- 不硬编码凭据；凭据由用例经 conftest 的 `credentials` fixture 注入（命令行 `--user/--password` 优先，其次环境变量），用例内不直接读 `os.environ`。

**2. 测试用例 `e2e/testcases/test_<功能>.py`（按功能模块拆分为独立类文件，一功能一类一文件）**：
- **一功能一类一文件**：每个功能模块对应**一个独立** `test_<功能>.py` 文件，文件内只含**一个** `class TestXxx`；**禁止**把多个功能 class 塞进同一个文件，也不把同一功能的场景散落为扁平测试函数。
- 文件命名：`test_<功能名>.py`，功能名为 snake_case；class 命名：`Test` + 功能名（PascalCase，与文件名对应，如 `test_home.py` → `class TestHome`）。
- `import pytest`、`import allure`、`import os`、按需 `from e2e.pages.<page>_page import <PageName>`；**测试文件只依赖页面对象，不直接 import `e2e.components` 下的组件类**。
- 用 `page` fixture（由 `e2e/testcases/conftest.py` 提供，**不自建 browser/context**）。
- `@allure.feature` 标注在 **class 级**（一个功能模块一个 feature，与文件/class 一一对应），`@allure.story` 标注在 **方法级**（每个需求场景一个 story），`@allure.severity` 标注在方法级。
- 凭据：沿用 `credentials` fixture 约定（conftest 注册 `--user/--password`，命令行 > `WEB_USER`/`WEB_PASS` 环境变量 > 占位值；用例只注入不直读环境变量；未提供则占位值自然失败）。
- 断言用原生 `assert` 比较页面对象返回的纯值，或调用页面对象的 `expect_xxx()` 断言方法；原始 Playwright API 禁止出现在用例。
- **参数化用例（强化约定）**：当 testcase.md 场景标注 `[参数化]` 且含「数据矩阵」时，必须满足：**同步骤、仅输入/预期值不同的多组数据合并为一条用例**，用 `@pytest.mark.parametrize` 展开，绝不逐条复制重复方法。
  - **数据源**：数据矩阵落盘为 `data/<module>.yaml`（与 `test_<功能>.py` 同名；顶层以场景名为 key 的 list of dict，每行含 `row_id` 及参数/预期字段），经根 `conftest.py` 的 `test_data` fixture 加载（如 `test_data["login_validation"]`）。
  - **用例形态**：用 `pytest.mark.parametrize("row", [pytest.param(c, id=c["row_id"]) for c in test_data["<场景名>"]], ...)` 展开；每个参数组合携带 `row_id` 作为用例 ID，并用 `@allure.title("...{row[row_id]}...")` 让 Allure 每个组合独立呈现、可反向追溯到 testcase.md 的 `行ID`。
  - **用例层零 Playwright API**：`row` 仅为纯数据，步骤与断言全部走页面对象通用方法（如 `fill_credentials(row["phone"], row["password"])` / `assert_validation(row["expected"])`），不得出现 locator / get_by_ / page.url / page.title。
  - 单条参数化方法统一标注一次 `@allure.story`/`@allure.severity` 即可，每个组合经 `row_id` 自动区分。
  - **预期结果可为多字段/多类型（通用，非仅登录）**：数据矩阵每行可同时携带多个预期字段（如 `expected_msg` / `expected_count` / `expected_url`），甚至用 `expected_type` 区分「成功跳转 / 错误提示 / 状态码」等不同结果性质。页面对象断言方法按行数据分支处理（如 `assert_result(row)` 内部依据 `row.get("expected_type")` 走不同断言路径），用例层仍只传 `row`、零 Playwright API。只要各数据行**步骤一致、仅数据与预期值不同**，无论功能域（搜索/筛选/表单/校验等）均可参数化，不局限于登录。
- **跨页流程用例**：用例内按步骤顺序实例化所需页面对象，同一 `page` 实例贯穿流程，不重复造 browser。
- **功能模块拆分依据（硬性约定）**：直接映射 **per-module `<模块>.testcase.md` 文件**——每一个 `<模块>.testcase.md` 对应一个 `test_<功能>.py` / `class Test<功能>`。文件命名 `<功能名>` 由 testcase.md 的「业务模块全名」派生为 snake_case（如 登录认证 → `test_login.py`）。`@allure.feature` 标注 **class 级且保留 testcase 的「业务模块全名」**（如 `@allure.feature("浏览发现")`）。模块内每个 `确定性 + READY` 场景 → 一个 `test_` 方法，**必须携带 testcase.md 的「`<模块名>-<实际业务名>`」用例 ID**（如 `@allure.testcase("登录认证-登入成功")` + `@pytest.mark.caseid(...)`，docstring 首行写明该用例 ID 与场景名）；用例 ID 一律沿用 testcase.md 原值，不得自行重编或省略。跨页面场景按 testcase.md 模块文件归属；testcase.md 未说明归属时退回修订，不自行判断。
- class 内**不含 `__init__`**；共享 fixture 统一放 `e2e/testcases/conftest.py`（如 `header`/`home`/`common_layer`/`logged_in_page`/`_credentials` 等），`test_data` 由框架初始化生成的项目根 `conftest.py` 提供（按模块名自动加载 `data/<module>.yaml`）；各 `test_<功能>.py` 文件**不在文件内重复定义 fixture**。
- 模块级常量若仅单功能使用可放该功能文件顶部；跨模块共享且非框架通用的**业务常量**统一放 `e2e/web/constants.py`，跨模块共享的**框架级共享常量**统一放 `config/config.yaml` 的 `web` 段；参数化数据集放 `data/`。

**强制三步生成顺序（硬性规则，不得跳步）**：
- **前置检查（三步前必做）：文件存在性扫描**——用 Glob 扫描 `e2e/pages/*.py` 与 `e2e/testcases/test_*.py`，列出已存在文件清单；**已存在文件默认不覆盖**，只补齐缺失方法/用例（方法体为 `NotImplementedError`/`pass` 的才回填）；内容发生变化时可修改；用户手改内容原则上不覆盖，冲突时报告交用户裁决；同名文件需全新建时追加版本后缀。
- **第 1 步：落所有页面类骨架**——按 testcase.md 中确定性+READY 场景涉及的页面创建全部 `<page>_page.py`（已存在的跳过新建，仅对缺失的页面建骨架）；每文件含 `class <PageName>(BasePage):` + docstring + **所有方法签名 + docstring**，方法体统一 `raise NotImplementedError` 或 `pass`；已存在文件若缺失方法签名只追加，签名需调整则同步修改；方法清单来源为场景中涉及该页的操作。**自检**：`py_compile` 全部骨架文件通过。
- **第 2 步：回填方法体**——逐个类、逐个方法填实现：定位器按本 Skill「定位器来源与强制验证」的两阶段法采集——阶段 0 静态推导本模块 `locator 需求表`（零 MCP）→ 阶段 1 按页/状态分组、每页仅一次 `navigate` + accessibility 快照、去重指纹复用、落盘 `spec/evidence/locators-<页>.json`；每个 locator 实测命中后写入并注释 `# 实测命中`；只回填 `NotImplementedError`/`pass` 占位方法；定位器强制验证、结构型定位器实测、禁止 `TODO_VERIFY` 占位/推迟自愈（缺 BASE_URL 或登录凭据则停止该场景并报告）。触发 AJAX 的方法点击后补 `wait_for_load_state("networkidle")`，原地 JS 刷新/分页类方法不包 `expect_navigation`。**自检**：`py_compile` 全部页面对象通过；`run_generator.py --check-locators` 扫描不得报「疑似未验证猜测」（含 `TODO_VERIFY` 一律判错）；回复末尾输出「已验证定位器清单」（每个 locator 的实测选择器与 `# 实测命中` 说明），**不得**输出「待验证/占位」清单。
- **第 3 步：写测试用例**——按 testcase.md 的 per-module 文件规划拆分（每模块 → 一个 `test_<功能>.py`），文件内写**一个** `class TestXxx` + 测试方法；已存在的 `test_<功能>.py` 默认不覆盖，只补缺失确定性+READY 场景（断言/步骤因更新需调整时可修改）；共享 fixture 统一落 `conftest.py`（既有则补缺失、不覆盖）；跨页流程按需注入多个页面对象，同一 `page` 实例贯穿；参数化场景抽离到 `data/<功能名>.yaml`；`@allure.feature` class 级、`@allure.story`/`@allure.severity`/`@pytest.mark.ui` 方法级。**自检**：`py_compile` 全部 `test_<功能>.py` + `conftest.py` 通过 + `pytest --collect-only -q` 成功 + **用例文件零原始 Playwright API**（grep `page.locator(`/`get_by_`/`sync_api`/`page.url`/`page.title` 在 `test_<功能>.py` 内零命中）。
- **不得跳步**：未完成第 1 步全部骨架前不得回填方法体；未完成第 2 步不得写用例。每步自检失败就修到通过再下一步。
- **代码风格**：PEP 8、类型注解、`# -*- coding: utf-8 -*-`、中文注释、`pathlib.Path`、UTF-8。

### Step 3：结果格式化（使用方式 + 幂等约定 + 交付）
**使用方式**：
- 串联调用：由 `playwright-pipeline-skill/scripts/run_full_pipeline.py` 自动调用本 Skill 的 `scripts/run_generator.py`。
- 单独调用（命令在项目根目录执行，或将 `PROJECT_DIR` 环境变量设为项目根）：
  ```powershell
  # 指定某一模块（推荐，按 testcase.md 格式）：脚本校验该模块文件并列出待生成功能
  python .codebuddy/skills/web-skills/06-playwright-generator-skill/scripts/run_generator.py spec/搜索.testcase.md
  # 或只传 feature，脚本自动 glob 该 feature 下全部 *.testcase.md 模块文件
  python .codebuddy/skills/web-skills/06-playwright-generator-skill/scripts/run_generator.py web_frontend
  ```
  脚本**只接受** testcase.md 模块文件；校验输入并列出模块后，由 LLM 按本 Skill 三步流程实现代码（可选参考 `templates/` 模板），仅依据 `确定性 + READY` 场景。

**幂等约定**：
- 已存在的 `<page>_page.py` / `test_<功能>.py` **默认不覆盖**，只补齐缺失方法/用例；但 testcase.md 更新导致内容需变化时，可修改对应代码段。
- 用户手改内容原则上不覆盖；与 testcase.md 冲突时报告并交回 testcase/用户裁决。
- **一页一类**：testcase.md 确定性+READY 场景新增页面时新建对应 `<page>_page.py`，不塞进既有类。
- **一功能一类一文件**：新增测试场景归入对应功能的 `test_<功能>.py` / `class TestXxx`；若该功能文件不存在则新建；**禁止**把新功能 class 塞进既有功能文件。
- **共享 fixture 集中管理**：跨功能共享的 fixture 统一落 `e2e/testcases/conftest.py`，已存在时只补缺失、不覆盖。

**产出后**：进入 `playwright-code-review-skill` 代码审核门禁，**通过才可执行 pytest**。

## ⚠️ 约束与规范

### 1. 代码规范（封装 / 页面对象 / 用例 / 定位器）
- 封装、复用优先、单一职责三条总原则贯穿始终；定位/等待/断言全部封装在页面对象，用例层零原始 Playwright API。
- 定位器语义化；**定位器强制实测命中（注释 `# 实测命中`）**，禁止猜测、禁止 `TODO_VERIFY` 占位、禁止推迟到自愈阶段（缺 BASE_URL/登录凭据则停止该场景并报告）。
- 等待与导航严格区分真实导航（`expect_navigation`）与原地 JS 刷新/分页（不包 `expect_navigation`）；async 内容不得裸断言；`target="_blank"` 用 `context.expect_page()` 捕获新页。
- 一页一类、一功能一类一文件；共享 fixture 只进 `conftest.py`、框架级共享常量只进 `config.yaml`、业务常量只进 `constants.py`、组件只供页面对象内部消费。

### 2. 安全边界
- 凭据（用户名/密码）来自用户指令或项目资料（用户指令优先），仅用于 MCP 定位会话或经 `credentials` fixture 注入，**绝不写入**生成文件/conftest/日志/截图/代码。
- 不复制或修改底座 `base_framework` 包，不触发底座 Skill；不覆盖用户已有实现，冲突时报告裁决。

### 3. 性能约束（幂等与三步门禁）
- 三步生成顺序不得跳步；每步自检（`py_compile` / `--check-locators` / `collect-only` / 零原始 Playwright API）失败就修到通过再下一步。
- 已存在文件默认不覆盖；并行执行时每个 xdist worker 独立创建浏览器资源，fixture teardown 必须释放资源。

### 4. 输出规范（产出边界）
- 产出 = N 个页面对象文件 + M 个测试用例文件（一个业务模块一个文件，与 `<模块>.testcase.md` 一一对应）；只按 `确定性 + READY` 场景生成，不得为填满覆盖面而实现未就绪场景。
- 不生成非用户要求的框架/用例项；不引入 `pytest-html`（除非用户明确要求）。

## ✅ 验证与自查

### 1. 功能校验
- 框架初始化：`compileall -q e2e conftest.py` 与 `pytest --collect-only -q` 通过；`runner.py` 若有则 `py_compile`。
- 三步生成每步自检通过：骨架 `py_compile` → 页面对象 `py_compile` + `--check-locators` 零疑似 → 用例 `py_compile` + `collect-only` + 用例文件零原始 Playwright API。
- 每个 `test_` 方法携带 testcase.md 用例 ID 与 `@allure` 标注；页面对象每个 locator 有 `# 实测命中` 注释。

### 2. 完整性校验
- 每个 `确定性 + READY` 场景均生成对应测试方法与页面对象方法；`NEEDS_CONFIRMATION`/`BLOCKED`/探索性场景未生成可运行用例。
- 共享 fixture 集中于 `conftest.py`，未在各用例文件重复定义；框架级共享常量集中于 `config.yaml`、业务常量集中于 `constants.py`，未在各用例文件硬编码。

### 3. 常见错误排查
- 猜测/占位定位器（未标 `# 实测命中`、又非来自 accessibility 语义快照实测的语义化定位，或分页/容器/弹层/总页数类）；`TODO_VERIFY` 占位或把采集推迟到自愈。
- 在 `conftest.py` / `runner.py` 注册 `--browser`/`--headed`/`--headless` 等 pytest 选项，与已安装的 `pytest-playwright` 等浏览器插件冲突（报 `option already added`），导致 pytest 启动即失败；浏览器类型/无头模式只由 `config.yaml` 的 `web.browser_type`/`web.headless` 驱动，不注册选项、不依赖环境变量。
- 用 `a[href=...]`、`:has-text(`、后代 `x a` 等会一对多的属性/文案选择器定位（同一 URL 的页头文字链与 CTA 按钮等多节点 → strict mode 多匹配违规）；应改用语义按名定位 `get_by_role(name=..., exact=True)` / `get_by_text`，且每个 locator 写入前用 `count()==1` 验证唯一并标 `# 唯一`。
- 异步内容裸断言（未等待 AJAX 渲染）；把原地 JS 刷新/分页误包 `expect_navigation` 导致超时；计数类断言把表头算成数据行。
- 用例层出现 `page.locator`/`get_by_`/`page.url` 等原始 Playwright API（未下沉到页面对象）。
- 把多个功能 class 塞进同一 `test_<功能>.py` 或扁平测试函数散落；凭据硬编码或落盘。

### 4. 最终确认
- 三步自检全过；`--check-locators` 零疑似；产出进入 `playwright-code-review-skill` 门禁（通过才可执行 pytest）；未就绪场景未提前生成。

## 📚 引用资源
- `python-pytest-base-framework`：外部 `base_framework` 包（日志/配置读取/报告/邮件/Allure），Web 层复用，不复制不修改。
- `references/locator-budget.md`：本 Skill 的 locator 实测节流附录（工具白名单、单页 1 快照预算、去重指纹、上下文收口、入口发现兜底）。
- `playwright-testcase-skill`：本 Skill 唯一业务输入来源（消费其 per-module `<模块>.testcase.md`）；输入不完整或不匹配时回流交由其修订，不回溯 planner skill。
- `playwright-code-review-skill`：下游代码审核门禁（本 Skill 产出后进入）。
- `playwright-healer-skill`：审核通过后执行与自愈下游。
- `playwright-pipeline-skill/scripts/run_full_pipeline.py` 与 `scripts/run_generator.py`：串联/单独执行入口（`--check-locators` 扫描疑似未验证定位器）。
