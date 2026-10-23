---
name: api-zero-code-framework
description: 生成「零代码 API 自动化框架」：框架具备日志、失败保留证据、生成 Allure 报告（含趋势 trend）、邮件通知、多环境、CI/CD 等能力；**新增一个 YAML 文件即新增一条用例（一个 business flow = 一个 case）**。以「单个 API 一个 YAML 文件」为可复用单元，业务文件用 steps 引用多个单 API 文件组合成链路（定义一次、多处复用）；每个 API 自带提取 + 多类型软断言；业务内某 API 失败则硬停止下游。当用户要做 API/接口自动化、零代码/数据驱动接口测试、用 YAML 管理可复用接口与业务链路时触发。只产出骨架与中性模板，不注入真实业务接口或账号。
---

## 🎯 角色与目标

你是高级测试开发工程师。在相对根 `./` 生成可运行的零代码 API 自动化框架，**让团队只靠写 YAML 就能做接口自动化**——新增一个 YAML 文件就新增一条用例，无需写 Python。

### 框架能力（生成即具备，开箱可用）
- **零代码用例**：`testcases/apis/`（单 API 组件）或 `testcases/flows/`（业务编排）放一个 `.yaml/.yml` 即被自动收集；同一份 API 可被多个 flow 用 `steps` 引用，`with` 覆盖本次调用。
- **多类型软断言**：`validate` 支持 equals/比较/包含/集合/长度/类型/正则/存在性/schema/状态码等；API 内全部执行后汇总。
- **链路硬停止**：业务内任一步骤失败 → 该 case 失败，后续步骤不再执行。
- **日志与可追溯**：每个 API 包为 Allure step，日志记「步骤 i/n · METHOD url [name] → 通过/失败」；失败自动保存请求/响应快照到 `artifacts/` 并挂载 Allure。
- **失败重试**：交由原生 `pytest-rerunfailures`（`pytest.ini` 的 `--reruns N --reruns-delay S`，默认各 1），`allure-pytest` 按 `historyId` 生成 Retries 视图。
- **邮件通知**：会话收尾按 `enable_email_report` 发送 HTML 摘要邮件（含完整失败现场），默认打包 Allure 报告 zip 附件；缺配置/异常仅告警不阻断。
- **多环境 & CI/CD**：`--env`/`TEST_ENV` 选 `data/<env>.yaml` 零改动切换；内置 `scripts/run_tests.py` + GitHub Actions / GitLab CI 示例。
- **Allure 报告**：结束生成 HTML（`Environment` 控件键名不含空格），复用 `history` 带趋势；开关 `enable_allure_report`/`auto_open_report`。
- **可提交 git**：运行产物由 `.gitignore` 排除，仅源码与 YAML 受版本管理。

依赖方向单向向下：`engine/ → common/ → utils/`。`common/` 提供公共 API：`ConfigReader / get_config / ApiClient / assert_spec / build_step_spec / run_flow`；报告与通知编排在 `engine/reporting/`：`build_summary / write_json_report / finalize_report_session / reset_allure_dir / attach_failure_artifact / attach_failure_text / generate_report / send_report_email`。**字段语义、断言类型、engine 契约、待生成源码均在 [reference.md](reference.md)（单一真相源），按契约实现。**

## 📋 前置条件与输入
1. 环境：Python ≥ 3.9；`pip install -r requirements.txt`（含 `requests`/`pyyaml`/`jsonpath-ng`/`jsonschema`/`pytest`/`pytest-xdist`/`allure-pytest`/`pytest-rerunfailures`）。失败重试由 `pytest-rerunfailures` 负责，无需框架自实现。
2. **Allure 报告前置**：`allure-commandline` CLI **且** Java(JRE/JDK 8+)。缺失时 `generate_report` 报错并给跨平台安装指引（或设 `ALLURE_BIN`）。
3. 必填输入（缺失则追问，禁止猜测）：相对根 `./`；被测 `base_url`（运行**必需**，在 `config/config.yaml`）；真实接口与账号由用户稍后提供，**本 skill 不注入**。
4. 知识基线：`requests.Session`、pytest 自定义收集、Allure、`多类型断言`、Allure 结果聚合。

## 🚶 工作流

> 生成任何文件前，先读 [reference.md](reference.md)：§零/§四/§五/§六/§七/§八/§十 含**待生成源码（单一真相源）**，第三/九节含字段与数据契约。

### Step 1：搭骨架与配置（先建目录、配置与入口）
幂等落地以下结构（仅写缺失文件）：
```
./
├── engine/                         # 零代码核心
│   ├── executor.py                 # build_step_spec + _run_single_api + _flatten_steps + run_flow（一个 flow=一个 case，逐步记日志）
│   ├── collector.py                # 一个 business flow = 一个 case（单 ApiItem）；仅 YAML；排除 apis/ 库
│   └── reporting/                  # 报告与通知编排（由 conftest 会话钩子驱动）
│       ├── report.py               # build_summary/write_json_report/finalize_report_session/reset_allure_dir/attach_failure_artifact/attach_failure_text
│       ├── mailer.py               # send_report_email/_build_html（HTML 摘要邮件，含失败现场，SSL/STARTTLS）
│       └── report_generator.py     # generate_report（Allure HTML，缺失给安装指引）
├── common/                         # 核心层 + 配置/上下文/数据/断言/脱敏/路径
│   ├── request_client.py           # ApiClient + ApiExecError
│   ├── assert_utils.py             # 多类型断言 + 软断言
│   ├── data_loader.py              # 加载 YAML 用例 + 环境常量
│   ├── context.py                  # 提取变量上下文（extract_global 跨业务共享）
│   ├── config_reader.py            # ConfigReader / get_config（进程内缓存）
│   └── paths.py                    # 集中项目路径（data/config/artifacts/allure-results），解耦 CWD
├── utils/
│   ├── dicts.py                    # deep_merge 字典深合并
│   ├── extract.py                  # JSONPath 提取（带默认值）
│   ├── templating.py               # ${var}/${env.X}/${read_yaml(X)} 模板解析
│   └── redact.py                   # 脱敏（请求/响应/证据/邮件统一覆盖敏感字段）
├── testcases/
│   ├── apis/                       # 单 API 定义库（可复用，不直接收集）
│   │   └── your_api.yaml           # 单 API 模板
│   └── flows/                      # 业务编排（被收集为用例）
│       └── your_flow.yaml          # 业务模板：steps 引用 apis
├── config/config.yaml              # 统一配置（base_url / 报告 / env / mail）
├── data/                           # 测试数据（与结构分离，按环境切换）
│   ├── share.yaml                  # 公共默认数据（methods/expect/default_headers 等；账号密码等敏感值不在此）
│   ├── dev.yaml                    # 开发环境覆盖（由 env 选择）
│   └── prod.yaml                   # 生产环境覆盖
├── scripts/                        # 运行脚本
│   ├── run_tests.py                # CI/CD 统一入口：清理结果/环境选择/报告/邮件/退出码
│   └── runner.py                   # pytest 启动器：透传参数给 pytest（python scripts/runner.py [pytest 参数]）
├── conftest.py                     # pytest_plugins=["engine.collector"] + 会话级报告（engine.reporting）；pytest.ini 功能开关在此注入；注册 --env 选项
├── .github/workflows/api-tests.yml # GitHub Actions 示例（push/PR/手动触发，上传 allure-results/report/junit 产物）
├── .gitlab-ci.yml                  # GitLab CI 示例（安装依赖→跑 scripts/run_tests.py→上传产物）
├── pytest.ini / requirements.txt / .gitignore
├── README.md                       # 框架说明与执行指引（如何定义用例、如何执行、CI/CD）
```

`pytest.ini`（固化 `--dist loadscope`：启用 xdist 并行时同一 flow 的步骤落在同一 worker，串行无副作用）：
```ini
[pytest]
testpaths = testcases
addopts = -ra --strict-markers --dist loadscope --alluredir=allure-results --reruns 1 --reruns-delay 1
# 日志：pytest 原生 logging（log_cli + log_file）；框架代码仅用 logging.getLogger
log_level = INFO
log_format = %(asctime)s [%(levelname)s] %(name)s: %(message)s
log_date_format = %Y-%m-%d %H:%M:%S
log_cli = true
log_cli_level = INFO
log_cli_format = %(asctime)s [%(levelname)s] %(name)s: %(message)s
log_cli_date_format = %Y-%m-%d %H:%M:%S
log_file = logs/pytest.log
log_file_level = INFO
log_file_format = %(asctime)s [%(levelname)s] %(name)s: %(message)s
log_file_date_format = %Y-%m-%d %H:%M:%S
filterwarnings =
    ignore::DeprecationWarning

# ===== 功能开关（true/false；环境变量可覆盖，见 conftest.py）=====
# ⚠️ bool 型开关行内一律不要写注释：pytest 会把整行当值解析，导致
#    ValueError: invalid truth value 'true   # 是否 allure generate'；注释必须单独成行写在开关上方
# 是否 allure generate
enable_allure_report = true
# 生成后是否自动打开（本地可设 true；CI 设 false）
auto_open_report = false
# 测试完成后是否发邮件（需 config.yaml 的 mail: 节）
enable_email_report = false

# ===== Allure 报告 =====
disable_test_id_escaping_and_forfeit_all_rights_to_community_support = True
# 失败重试 = pytest-rerunfailures（addopts 见上行）；并行追加 `-n auto`；多环境用 --env/TEST_ENV
```

`.gitignore` 必须排除运行产物，保证**可提交 git**：`logs/` `reports/` `allure-results/` `artifacts/` `.pytest_cache/` `__pycache__/` `*.pyc` `*.zip` `venv/` `.venv/` `.env`；`scripts/run_tests.py`、`.github/`、`gitlab-ci.yml` 等 CI 配置**应提交**；仅源码与 YAML 用例受版本管理。

### Step 2：落地 `common/` 支撑模块（源码在 reference.md）
按 [reference.md](reference.md) §零「common/ 模块源码」原样写入下列模块（仅写缺失）；公共 API 见各模块签名；它们只依赖 `requirements.txt` 已声明三方包（`requests`/`pytest`/`allure-pytest` 等），不引入额外依赖：
- `config_reader` / `request_client` / `context` / `data_loader` / `paths` / `redact`（报告与通知在 `engine/reporting/`：report/mailer/report_generator）

### Step 3：engine/ 核心（一个 flow = 一个 case）
按 [reference.md](reference.md) §七（executor.py 源码）、§八（collector.py 源码）、§六（assert_utils.py 源码）实现：
- `engine/collector.py`：pytest 插件，递归展开 `flows/` 为 `业务title :: API name` 的 `ApiItem`；**仅收集 `flows/`**，`apis/` 不直接收集；被复用业务文件加 `component: true` 跳过直接收集；`pytest_plugins=["engine.collector"]` 在 `conftest.py` 注册。
- `engine/executor.py`：`run_flow` 顺序执行 steps；每个 API 包为 Allure step，记「步骤 i/n」日志；失败保存请求/响应快照到 `artifacts/` 并 `attach_failure_artifact` + `attach_failure_text('失败详情-...')`；API 内软断言汇总，业务内任一失败 `run_flow` 返回、下游 step 不再执行（硬停止）。
- 依赖方向：`engine → common → utils`，`engine` 不 import 具体接口名。
- **失败日志必须完整可对照**（格式见 [reference.md](reference.md) §七）：失败时除「步骤 i/n」行外，输出 `接口[名称] / 请求(头/体) / 响应(状态码耗时/头/体) / 错误`，URL 用完整地址、敏感字段脱敏；断言失败项形如 `期望 == '200' (str) | 实际 '1004' (str)  （取值: 响应 $.code）`（**期望与实值均带类型**）。

### Step 4：模板（零代码 YAML，详见 reference.md）
完整「单 API 模板」与「业务模板」YAML 见 [reference.md](reference.md) §一（单一真相源），生成时**原样套用**其结构（模板内 `<...>` 均为占位符，生成后按真实业务替换）；要点：
- 单 API 文件（如 `testcases/apis/login.yaml`）：`name` + `request`（method/url/headers/体）+ `extract_global` + `validate`；一个文件 = 一个可复用 API。method 用 `data/share.yaml` 的方法常量 `${POST}`/`${GET}`，避免硬编码大小写。
- 业务文件（如 `testcases/flows/查询我的书架.yaml`）：`title` + `steps`（顺序 `include` 单 API / 子业务），`with` 覆盖本次 `request` 与 `validate`/`extract`/`extract_global`。`with` 推荐写法是**顶层直平铺**（`{url:..., form:..., validate:...}`），也兼容 `with.request` 嵌套写法。
- 复用（三层）：① `apis/` 一份文件可被多个 `flows/` `include`；② `flows/` 一份业务文件也可被另一份 `flows/` `include`（嵌套业务，递归展开为 `父业务 :: 子业务 :: API`；被复用的业务文件顶部加 `component: true`，收集器跳过其直接收集）；③ `with` 可覆盖本次调用的 `request`（`json`/`params`/`headers`）**以及** `validate`/`extract`/`extract_global`，衍生正向/反向用例。
- 共享：同业务内上游 `extract`/`extract_global` 对下游直接可见；跨业务用 `extract_global` + `${read_yaml(name)}`。
- 断言/硬停止/数据外部化：见 reference.md 第三、八、九节。**能用常量替代的值都进 `data/`**（method/url/headers/body/预期码/账号密码等，环境 Profile 深合并），用例用 `${...}` 引用；仅「结构/逻辑」（steps 编排、断言类型、actual 取值路径、extract 规则）留用例文件。数据分层：`share.yaml` 放**跨环境一致**的公共默认（方法常量/expect 码/default_headers 等），`dev.yaml`/`prod.yaml` 放**环境专属**值并由 `env` 选择深合并覆盖；**账号密码/token 等敏感值只放 `data/<env>.yaml`，不要放 `share.yaml`**。

### Step 5：README
根目录产出 `README.md`。**必须含「如何添加测试用例」一节**（复用 Step 4 模板：在 `testcases/apis/` 建单 API YAML，再在 `testcases/flows/` 用 `steps` 引用；强调「新增一个 YAML 即新增一条用例」，无需改 Python），并含「CI/CD」一节（`scripts/run_tests.py` 用法、`--env`/`TEST_ENV` 环境切换、流水线产物 allure-results/report/junit）。**执行无需 mock**——`config.yaml` 配 `base_url` 指向真实被测服务即可真实发请求并断言；若未配置 `base_url`，运行直接报错（明确提示「base_url 未配置」），**不收集、不 skip**，禁止无服务时空跑。README 须自包含，不得引用 `reference.md` 或 skill 内部文档（它们不在生成框架内）。

### Step 6：自检
- `python -m compileall engine common utils conftest.py scripts` 全过（勿用 `py_compile engine/*.py`，PowerShell 不展开通配符）。
- `pytest --collect-only`：**每个 `flows/` 文件收集为一个 `ApiItem`（Item 名 = flow 的 `title`）**；`apis/` 文件不直接收集；且**不出现 `ValueError: invalid truth value`**（出现即说明 `pytest.ini` 的 bool 开关写了行内注释）。
- 失败日志格式（必看，对照参考实现）：故意让某 API 断言失败，确认日志为：
```
2026-10-20 17:05:10 [ERROR] engine.flow: 步骤 1/2 失败，硬停止后续步骤 [登录接口]
接口[登录接口]
  请求: POST http://host/user/login
    头: {...}
    体: {...}
  响应: HTTP 200 (82.2ms)
    头: {...}
    体: {...}
  错误: ❌ 业务「查询我的书架」· API「登录接口」断言失败：共 1 项未通过
  1. [equals · 业务码为200] 期望 == '200' (str) | 实际 '1004' (str)  （取值: 响应 $.code）
```
  且 `ApiItem.repr_failure` 返回 `str(excinfo.value)`（不再附加框架堆栈）；`setattr(e, "details", detail)` 把同一段 detail 透传到 `run_flow` 的 ERROR 日志与 Allure 失败详情附件。
- 断言类型自测（必做，防止类型分派漏项）：用一个返回 `{"code":"200"}` 的接口跑一遍，至少覆盖 `status_code` / `equals` / `greater_than` / `contains` / `length` / `type` / `regex` / `exists` / `schema`，并故意让 2 条失败，确认汇总信息含类型/名称/期望/实际/取值路径；**期望/实值都带类型**（`期望 == '200' (str) | 实际 '1004' (str)`）。尤其确认 `status_code` 不会落「未知断言类型」（症状：HTTP 明明 200 却报 `未知断言类型 'status_code'`）。
- 检索确认：发请求仅出现在 `common/request_client.py`；用例为「单 API 文件 + flows 引用」结构；日志/报告等配套模块位于 `common/`。
- **提取链路必跑（必做，防止 `too many values to unpack` 运行期崩溃）**：至少一条用例须带 `extract`/`extract_global`（如 `extract_global: { token: [json, $.data.token, ""] }`）并真实执行，确认 `parse_extract` 的 **3 元组 `(mode, path, default)`** 被正确解包（`_run_single_api` 里必须是 `_mode, jp, default = parse_extract(val)`，绝不能写成 `jp, default = ...`）。`reference.md` §四已注明返回 3 元组，调用处务必匹配。

## ⚠️ 约束
1. 零代码边界：业务完全由 YAML 表达（单 API 定义 + 业务 `steps` 引用），不含 Python 测试代码。
2. 单 API 文件 + 业务组合复用（唯一模型）：「单个 API 一个文件（`apis/`）+ 业务 `steps` 引用（`flows/` 或嵌套另一份 `flows/`）」；跨接口关联用 `extract_global` + `${read_yaml(name)}`；参数/断言差异用 `with`。
3. 仅 YAML：用例文件只支持 `.yaml`/`.yml`；YAML 里的 `json:` 仅指 HTTP 请求体类型，与用例文件格式无关。
4. 多类型软断言 + 链路硬停止：规则与错误信息格式以 reference.md 第三、八节为准。
5. 日志/配置/报告/邮件由 `common/` 模块提供（源码见 reference.md §零），只依赖 `requirements.txt` 已声明三方包，不引入额外依赖。
6. 鉴权单点：Token/请求头注入只在 `common/request_client.py`。
7. 断言可追溯：`validate` 以声明式写在 YAML 中。
8. 中文 UTF-8。
9. 配置分层：`config/config.yaml` 配置 `base_url`/报告目录/数据/`env`/`mail`；`pytest.ini` 统一功能开关（`enable_allure_report`/`auto_open_report`/`enable_email_report`）；失败重试由 `pytest-rerunfailures` 的 `--reruns`/`--reruns-delay` 负责、并行可选（`addopts` 追加 `-n auto`，依赖 pytest-xdist）。**环境变量覆盖仅在「非空」时生效：空字符串/未设置均回落配置文件（避免 CI 中未设置的 secret 解析为空串吞掉 `base_url` 等配置）。**
10. base_url 缺失即报错：若 `config.yaml` 未配置 `base_url`，运行直接抛配置错误（pytest 失败/error），不收集、不 skip，禁止无服务时空跑。**`BASE_URL` 为空环境变量不算已配置、也不会覆盖 `config.yaml` 的 `base_url`（空 env 回落配置，非空 env 仍可正常覆盖）。**
11. 默认请求头单一来源（数据化）：全局默认头定义在 `data/share.yaml` 的 `default_headers`，由 executor 作为默认层注入；各 feature 可在 `data` 下用 `headers` 补充/覆盖（自动合并到默认头）；单 API 的 `request.headers` 与业务 step 的 `with.headers` 再叠加（覆盖同名）。合并优先级：`default_headers < feature.headers < request/with.headers`。鉴权单点（`Authorization`）仅在尚无时注入，不覆盖既有值。
12. 数据与结构分离：**能用常量替代的值都进 `data/`**，用例用 `${...}` 引用；仅「结构/逻辑」留用例文件。分层：`share.yaml` 只放跨环境一致的公共默认（方法常量/expect 码/default_headers 等）；**账号密码/token 等环境专属敏感值只定义在 `data/<env>.yaml`（如 `data/dev.yaml`），不要写入 `share.yaml`**，由 `env` 深合并覆盖。
13. 规避常见坑（体类型/业务码字符串/404/token 鉴权/并行）：生成用例与排障遵循 reference.md 第十一节；`equals` 对「字符串 vs 数字」数值宽容；`executor` 支持 `json`/`form`/`data`/`files` 四种体；`Authorization` 可能需裸 token 或 Bearer，以 Apifox/DevTools 实证为准；并行默认 `--dist loadscope` 且 `extract_global` 不跨 worker。
14. 报告开关独立：`enable_allure_report` 控制是否 `allure generate`，`auto_open_report` 控制是否 detached `allure open`，`enable_email_report` 控制是否发邮件（环境变量 `ENABLE_EMAIL_REPORT` 可覆盖）。失败重试交由 `pytest-rerunfailures`（`--reruns N --reruns-delay S`，默认各 1），不自行实现重跑；`report.py` 仍按 `historyId` 聚合去重（最终一次为结果），case 只体现最终状态（passed/failed），不增加计数、不保留重试中间态。
15. 多环境零改动：`--env dev/prod` 或环境变量 `TEST_ENV` 选择 `data/<env>.yaml`（优先级 `--env` > `TEST_ENV` > `config.yaml` 的 `env` > `dev`），CI 用 `scripts/run_tests.py --env <env>` 即可切换。
16. 邮件不阻断：`engine.reporting.send_report_email` 缺 `smtp_host`/`receivers` 或发送异常仅 `logging.warning` 并返回 `False`，绝不抛异常、不影响用例；`smtp_password` 用环境变量 `MAIL_SMTP_PASSWORD` 注入，勿提交明文。
17. **断言类型分派必须完整**：`_check` 要覆盖第三节全部类型**及其别名**（`eq/ne/gt/lt/gte/lte/matches`）+ `status_code`/`status` 独立分支（actual 隐含为 `resp.status_code`）。漏分派会落「未知断言类型」分支，出现「HTTP 200 正确却断言失败」假失败。别名表与分派写法见 reference.md §六。
18. **`pytest.ini` 的 bool 型 ini 值禁止行内注释**：`enable_allure_report`/`auto_open_report`/`enable_email_report` 注册为 `type="bool"`，行内 `# ...` 会被 pytest 当作值的一部分，导致 `ValueError: invalid truth value`；注释只能单独成行写在开关**上方**。

## ✅ 验证
1. `py_compile` 全过；`pytest --collect-only` 收集 `flows/` 为单个 Item（Item 名 = title），`apis/` 不直接收集。
2. 检索：发请求仅在 `request_client.py`。
3. 多类型断言验证：混合多类型并故意让两条失败，错误信息含类型/名称/期望/实际/取值路径，期望/实值带类型（`(str)`/`(int)`）。
4. 软断言验证：一个 API 内所有断言均执行（汇总含全部失败项）。
5. 链路硬停止验证：让某 API 断言失败，确认 ①日志输出 `步骤 i/n 失败，硬停止后续步骤 [name]` + 完整 `接口[名]/请求/响应/错误` 块；②后续步骤日志输出 `⏭️  API「x」已跳过：上游 API『y』执行失败，已停止执行本业务后续 API`；③pytest 报告（`repr_failure`）只展示可读摘要（不附堆栈）；④Allure 失败详情附件含同一段 detail（`attach_failure_text`）。
6. 复用验证：同一份 `apis/` 文件被多个 flow `include`；`with` 覆盖不影响其它引用。
7. 状态断言验证：`- status_code: { expected: 200 }` 在真实返回 200 时必须通过（无「未知断言类型」）。
8. 配置解析验证：`pytest --collect-only` 无 `invalid truth value` 报错（bool 开关无行内注释）。
9. 重试验证：故意让一个 case 失败，确认 `RERUN [n%]` 出现一次（`pytest-rerunfailures`），最终仍失败；`report.json` 的 `total` 不含重试中间态（`historyId` 聚合去重）。
10. Content-Type 驱动体编码验证：headers 写 `Content-Type: application/x-www-form-urlencoded`、body 用 `form:` → 实际请求走 `data=`；用 `json:` + Content-Type json → `json=`。

- [ ] 目录结构与树一致
- [ ] `apis/` 单 API 文件可复用；`flows/` 用 `steps` 引用
- [ ] 收集只收集 `flows/`（展开多 Item），`apis/` 不直接收集
- [ ] `common/` 与 `utils/` 按 reference.md §零 源码生成（config_reader/request_client/context/data_loader/paths/redact）；`engine/reporting/` 生成报告三件套（report/mailer/report_generator）
- [ ] 新增 YAML 即被收集为用例（无需改 Python）；`.gitignore` 已排除 logs/reports/allure-results/artifacts
- [ ] 失败用例在 `artifacts/` 留证并挂载 Allure；生成报告带 `history`（趋势）
