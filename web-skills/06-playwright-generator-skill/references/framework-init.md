# 框架初始化详细说明（generator · Step 1）

> 本文件是 `SKILL.md` 中「Step 1：框架初始化」的详细附录。**仅在执行框架初始化模式时按需阅读**；POM 用例生成模式无需加载本文件，以节省上下文。

## 初始化约定

### requirements.txt
声明 pytest、pytest-xdist、allure-pytest、PyYAML、python-dotenv、Playwright、pytest-rerunfailures；日志、配置读取、报告汇总、邮件发送等通用能力由 `utils/` 提供；安装浏览器使用 `python -m playwright install chromium`（按 `web.browser_types` 安装所需引擎，如 `firefox`/`webkit`）。

### config/config.yaml
包含 `web`、`report`、`email` 配置（可选 `auth.test_user` 仅存账号用户名）。`web` 段承载**框架级共享常量**（与具体业务/数据无关的通用值，可经环境变量覆盖）：如 `base_url`、`browser_types`、`headless`、`trace_enabled`、`default_timeout`、`network_idle_timeout`、`retry_count`、通用等待状态名、固定日志/断言文案等——这些值**不再硬编码在 `common/constants.py`**，改由 `utils.config_reader.ConfigReader` 读取。默认 `headless: true`、`report.auto_open: false`、`email.enabled: false`；SMTP 密码、**测试账号密码**等敏感值只经环境变量/命令行注入，**不写入本文件**。

`web` 段示例（框架级共享常量，模板层给通用默认值，生成时按项目资料覆盖）：

```yaml
web:
  base_url: ''
  browser_types: ['chromium']
  headless: true
  trace_enabled: true
  default_timeout: 30000        # 元素操作默认超时（毫秒）
  network_idle_timeout: 5000    # 网络空闲等待（毫秒）
  retry_count: 2                # 失败重试次数
  wait_states:                  # 通用等待状态名（Playwright 状态）
    - 'load'
    - 'domcontentloaded'
```

### 配置渲染（占位符替换，密码不落盘）
框架初始化模式生成 `config/config.yaml` 时以 `templates/config.yaml.template` 为蓝本。模板层只保留通用占位符（`__BASE_URL__`、`__TEST_USER__`、`__BROWSER_TYPE__`、`__HEADLESS__`）。生成时从项目资料读取**真实**值替换，均直接写入、不留占位符：`__BASE_URL__` → 真实 Web 前台连接地址、`__TEST_USER__` → 真实测试账号用户名；`__BROWSER_TYPE__` → 浏览器引擎（chromium/firefox/webkit，可扩展为多种，如 `['chromium','firefox']`），`__HEADLESS__` 默认 `true`。**密码绝不写入本文件**：运行期经 `credentials` fixture 由命令行 `--password` 或环境变量 `WEB_PASS` 注入（命令行优先），详见 `tests/conftest.py`。

### pytest.ini
默认内容（生成时直接写入，确保中文/特殊字符用例 ID 原样保留；`addopts` 固化 `--alluredir`/`-n auto`/`--reruns` 等运行参数）：

```ini
[pytest]
testpaths = tests
addopts = --alluredir=allure-results -n auto --reruns 2
markers =
    ui: Web UI 用例
    smoke: 冒烟用例
disable_test_id_escaping_and_forfeit_all_rights_to_community_support = True
```

该属性关闭 pytest 默认的用例 ID 转义，避免中文用例名（如 `test_login[登录成功]`）被转成不可读编码；注册 `ui`/`smoke` 等标记以避免 PytestUnknownMarkWarning。`addopts` 固化 `--alluredir`（Allure 结果目录）、`-n auto`（pytest-xdist 并行）、`--reruns 2`（失败重试）；要调整并行度/重试直接改此处或命令行覆盖。

### data/
存放测试数据（参数化用例的数据源，YAML/JSON/CSV）。每个功能模块对应一个 `data/<module>.yaml`（`<module>` 为测试模块名，如 `test_login.py` → `data/test_login.yaml`，与 `test_<功能>.py` 同名），由框架初始化生成的项目根 `conftest.py` 的 `test_data` fixture 按调用测试模块名自动加载（实现见 `conftest.py.template`）；框架初始化创建 `data/` 空目录（不预建示例数据文件），不在用例文件内硬编码大段输入数据。

### BrowserManager（common/browser_manager.py）
负责 Playwright/browser/context 生命周期；`viewport` 配置在 `browser.new_context()`；浏览器类型/无头模式**只由 `config.yaml` 的 `web.browser_types` / `web.headless` 驱动**（`browser_types` 为列表，支持多种浏览器引擎，默认列表首项；要变更改配置或配置 profile）。**严禁注册 `--browser`/`--headed`/`--headless` 等 pytest 选项、也不得依赖 `WEB_BROWSER_TYPE`/`WEB_HEADLESS` 环境变量**——运行环境常已安装 `pytest-playwright` 等插件并注册了同名选项，重复 `addoption` 会触发 `option already added` 导致 pytest 启动即失败。按 `web.trace_enabled` 启动 trace，失败时导出到 `traces/`。`screenshots/` 与 `traces/` 按需创建：截图与 trace 落地前由对应代码 `Path(...).mkdir(parents=True, exist_ok=True)` 创建。

### BasePage（base/base_page.py）
包装导航、点击、输入、读取、断言和截图等常用操作，使用日志和 `allure.step`；页面对象继承 `base.base_page.BasePage`。导航统一调用基类 `goto()`（基于类级 `URL_PATH`：无参走 `URL_PATH`、传 `path` 覆盖）；**禁止生成 `open()` 调用**——框架 `BasePage` 不提供 `open()`，调用会在运行时抛 `AttributeError`，测试模板与页面对象均改用 `goto()`。

### common/constants.py
集中定义**业务相关常量**（与具体业务/页面语义强相关的常量）：如业务状态码、业务文案/枚举、页面固定业务标识、业务阈值等；**框架级共享常量（超时、等待状态、重试次数、通用日志/断言文案等）一律进 `config/config.yaml` 的 `web` 段，经环境变量覆盖，禁止在 constants.py 硬编码**。页面对象与用例统一 `from common.constants import ...` 引用业务常量，**禁止在页面对象或用例中硬编码这些业务常量**；框架级通用值由 `ConfigReader`（`utils.config_reader`）从 `config.yaml` 读取；仅单功能使用、与业务数据强相关的常量可放功能文件顶部或 `data/`，真正跨模块共享的业务常量才进 `constants.py`。

### 根 conftest.py
提供 session 生命周期与路径注入；失败截图/失败挂载由 `pytest_runtest_makereport` hook 处理（call 阶段 failed/broken），显式导入 `Path`，将截图附加到 Allure，trace 由 `BrowserManager.export_trace()` 导出后使用 `utils.report.attach_failure_artifact("trace", trace_path)` 挂载；采集或挂载失败不得掩盖测试原始结果。

### fixture 作用域约束（防 ScopeMismatch）
被 session 级消费者请求的 fixture 必须声明 `scope="session"`（至少不低于消费者）。已知冲突：`pytest-base-url` 插件的 session 级 `_verify_url` 会请求 `base_url`——`base_url` 若为 function 级将报 `ScopeMismatch`。`base_url` 等包装 session 级资源（如 browser_manager）的 fixture 一并声明 session 级。

### 凭据注入（来源：用户指令或项目资料）
登录凭据的来源优先级为「用户指令显式给出 > 项目资料（`auth` 段）」，任一提供即可。`tests/conftest.py` 注册 `pytest_addoption`（`--user` / `--password`，可带 `--pass` 别名）；`credentials` fixture 取值优先级为「命令行 > 环境变量（项目约定名如 `WEB_USER`/`WEB_PASS`）」，任一来源提供即可（凭据实际值同源用户指令或项目资料，但**不写入** `tests/` 下任何文件与日志）；均未提供时用占位值让登录用例自然失败。生成阶段若需 MCP 登录以采集需鉴权页面的 locator，同样取该凭据用于本次 MCP 会话，用完即弃、不落盘。

### session 钩子
`pytest_sessionstart` 调用 `utils.report.reset_allure_dir(session, "allure-results")`；`pytest_sessionfinish` 调用 `utils.report.finalize_report_session(session, env=..., auto_open=..., email_enabled=...)`，显式传入配置开关。以 `utils.report` 现有并行安全逻辑收尾，不自行重复生成报告或发邮件；邮件默认关闭。`BrowserManager` 记录浏览器 brand/version/headless 信息供报告环境信息使用。并行执行时每个 xdist worker 独立创建浏览器资源，fixture teardown 必须释放资源。

### 空目录约定
`pages/`、`components/`、`tests/` 在框架初始化时为空目录（不预置示例）；首个页面/功能用例由 POM 生成阶段按 `testcase.md` 创建，避免代码审核将无关文件判为清单外残留；**默认空套件天然跳过，不可故意失败**（不访问外网）。

## 初始化验证
在目标项目根目录安装依赖、安装选用的 Playwright 浏览器，然后运行：

```powershell
python -m compileall -q .
python -m pytest --collect-only -q
```

报告检查以机器可读的 `report.json` 和 Allure 结果文件为准；不安装 Allure CLI 时不宣称已生成 HTML 报告。不得发送真实邮件或访问真实账号来证明骨架可运行。

## CI/CD 与邮件发送（框架初始化一并生成）

- **CI/CD（默认 GitHub Actions）**：框架初始化在 `<PROJECT_DIR>/.github/workflows/ci.yml` 生成可运行工作流（仅当用户要求时再按需切换为 GitLab/Jenkins，不并行加平台）。规则：push / PR / 手动触发；Python 矩阵按 `requires-python`（≥3.9）；缓存 pip；步骤为 `py_compile` 全部根级模块 + `pytest` + 失败时 `if: always()` 归档 `allure-results/` 与 `report.json`；**不在源码/工作流写 Secrets**，Allure HTML 不默认装 CLI（无 CLI 时归档原始结果 + JSON 汇总）；**默认关闭**自动开浏览器与发邮件（`AUTO_OPEN_REPORT=false`、`SEND_REPORT_EMAIL=false`）。邮件仅在用户在仓库 Secrets 配好 SMTP 后再开。
- **邮件发送（内化于 `utils/email_sender.py`）**：`EmailSender().send_report(summary)` 用标准库 `smtplib` 发送三段式 HTML 报告（环境信息→统计条→用例明细，内联失败截图），不引入第三方邮件依赖；SMTP 主机/端口/账号/收件人取自 `config.yaml` 的 `email` 段，SMTP 授权码经环境变量 `EMAIL_AUTH_CODE` 注入、**不落盘**。发送失败 `logger.error` 吞异常、不阻断用例结果。触发点：根 `conftest.py` 的 `pytest_sessionfinish` 调用 `utils.report.finalize_report_session(...)` 时，若 `email_enabled` 为真则内部调用 `EmailSender` 发送；`email_enabled` 缺省回退环境变量 `SEND_REPORT_EMAIL`（默认 false）。
- **运行入口统一用 pytest**：并行（`-n auto`）与失败重试（`--reruns 2`）已固化在 `pytest.ini` 的 `addopts`，要调整并行度直接改 `pytest.ini` 或命令行覆盖。
