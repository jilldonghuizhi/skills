---
name: api-zero-code-framework
description: 生成「零代码 API 自动化框架」：框架具备日志、失败保留证据、Allure 报告（含趋势）、邮件通知、多环境、CI/CD 等能力；**新增一个 YAML 文件即新增一条用例（一个 business flow = 一个 case）**。以「单个 API 一个 YAML 文件」为可复用单元，业务文件用 steps 引用多个单 API 文件组合成链路（定义一次、多处复用）；每个 API 自带提取 + 多类型软断言；业务内某 API 失败则硬停止下游。当用户要做 API/接口自动化、零代码/数据驱动接口测试、用 YAML 管理可复用接口与业务链路时触发。只产出骨架与中性模板，不注入真实业务接口或账号。
---

## 🎯 角色与目标

你是高级测试开发工程师。在相对根 `./` 生成可运行的零代码 API 自动化框架，**让团队只靠写 YAML 就能做接口自动化**——新增一个 YAML 文件就新增一条用例，无需写 Python。

### 框架能力（生成即具备，开箱可用）
- **零代码用例**：`testcases/apis/`（单 API 组件）或 `testcases/flows/`（业务编排）放一个 `.yaml/.yml` 即被自动收集；同一份 API 可被多个 flow 用 `steps` 引用，`with` 覆盖本次调用。
- **多类型软断言**：`validate` 支持 equals/比较/包含/集合/长度/类型/正则/存在性/schema/状态码等；API 内全部执行后汇总。
- **链路硬停止**：业务内任一步骤失败 → 该 case 失败，后续步骤不再执行。
- **日志与可追溯**：每个 API 包为 Allure step；失败自动保存请求/响应快照到 `artifacts/` 并挂载 Allure。
- **失败重试**：交 `pytest-rerunfailures`（`pytest.ini` 的 `--reruns N --reruns-delay S`，默认各 1），按 `historyId` 去重。
- **邮件通知**：`enable_email_report` 时发 HTML 摘要邮件（缺配置/异常仅告警不阻断）。
- **多环境 & CI/CD**：`--env`/`TEST_ENV` 选 `data/<env>.yaml` 零改动切换；含 `scripts/run_tests.py` + GitHub Actions / GitLab CI 示例。
- **Allure 报告**：结束生成 HTML（Environment 键名不含空格），复用 `history` 带趋势；开关 `enable_allure_report`/`auto_open_report`。
- **可提交 git**：运行产物由 `.gitignore` 排除，仅源码与 YAML 受版本管理。

> **关键改动（省 token）**：所有框架源码（`engine/`、`common/`、`utils/`、`scripts/`、`conftest.py`、配置、模板、CI）已固化为 `templates/` 下的静态文件，由 `scaffold.py` 一键复制到目标目录。**不要逐字重新生成 Python 源码**——直接运行 `scaffold.py` 即可，保证产物字节级一致、且不在上下文中再生代码。写用例的语义见 `reference_contract.md`（按需懒加载）。

## 📋 前置条件与输入
1. 环境：Python ≥ 3.9；`pip install -r requirements.txt`（含 `requests`/`pyyaml`/`jsonpath-ng`/`jsonschema`/`pytest`/`pytest-xdist`/`allure-pytest`/`pytest-rerunfailures`）。
2. **Allure 报告前置**：`allure-commandline` CLI **且** Java(JRE/JDK 8+)。缺失时 `generate_report` 报错并给跨平台安装指引。
3. **必填输入（缺失则追问，禁止猜测）**：相对根 `./`；被测 `base_url`（运行**必需**，写入 `config/config.yaml`）；真实接口与账号由用户稍后提供，**本 skill 不注入**。

## 🚶 工作流

### Step 1：收集输入与生成骨架
向用户确认 `./` 根目录与 `base_url`（env 默认 `test`，四选一：dev/test/staging/prod）。然后运行脚手架（仅标准库，无需依赖）：

```bash
python <skill_dir>/scaffold.py --root <目标目录> --base-url <base_url> --env test
```

`scaffold.py` 会把 `templates/` 全量复制到目标目录，并把 `base_url`/`env` 注入 `config/config.yaml`。**幂等**：仅写缺失文件、覆盖配置占位。
- 目录结构（已生成）：`engine/`（executor/collector/reporting）、`common/`、`utils/`、`testcases/{apis,flows}/`（放你的真实用例）、`examples/`（写法参考骨架，不收集）、`config/`、`data/{share,dev,test,staging,prod}.yaml`、`scripts/`、`conftest.py`、`.github/workflows/api-tests.yml`、`.gitlab-ci.yml`、`pytest.ini`/`requirements.txt`/`.gitignore`/`README.md`。
- `pytest.ini` 已固化 `--dist loadscope` 与 `--reruns 1 --reruns-delay 1`；bool 开关的注释均**单独成行**在开关上方（pytest 会把行内注释当值 → `ValueError: invalid truth value`）。

### Step 2：编写用例（按需读契约）
仅当用户要编写/调整 YAML 用例时，才读 `reference_contract.md`（字段语义、断言类型、变量 `${...}`、常见坑）。要点：
- 单 API 文件（`testcases/apis/*.yaml`）：`name` + `request`（method 用 `${POST}`/`${GET}` 常量）+ `extract_global` + `validate`；一个文件 = 一个可复用 API。
- 业务文件（`testcases/flows/*.yaml`）：`title` + `steps`（顺序 `include` 单 API / 子业务），`with` 覆盖本次 `request` 与 `validate`/`extract`/`extract_global`（兼容顶层直平铺与 `with.request` 嵌套）。
- 复用三层：① `apis/` 被多个 `flows/` `include`；② `flows/` 被另一份 `flows/` `include`（顶部加 `component: true` 跳过直接收集）；③ `with` 衍生正向/反向用例。
- 数据与结构分离：能用常量替代的值都进 `data/`（method/url/headers/body/预期码/账号密码等，`share ⊕ env` 深合并）；**账号密码/token 等敏感值只放 `data/<env>.yaml`，不进 `share.yaml`**。用例用 `${...}` 引用。

### Step 3：README
`README.md` 已由脚手架生成（含「如何添加测试用例」「CI/CD」），无需再写。

### Step 4：自检
- `python -m compileall engine common utils conftest.py scripts` 全过（勿用 `py_compile engine/*.py`，PowerShell 不展开通配符）。
- `pytest --collect-only`：每个 `flows/` 文件收集为一个 `ApiItem`（Item 名 = flow 的 `title`）；`apis/` 不直接收集；不出现 `ValueError: invalid truth value`。
- 失败日志格式：故意让某 API 断言失败，确认日志为 `步骤 i/n 失败，硬停止后续步骤 [name]` + 完整 `接口[名]/请求/响应/错误` 块；`repr_failure` 返回可读摘要（不附堆栈）；Allure 失败详情附件含同一段 detail。
- 断言类型自测：用一个返回 `{"code":"200"}` 的接口跑一遍，覆盖 `status_code`/`equals`/`greater_than`/`contains`/`length`/`type`/`regex`/`exists`/`schema`，故意让 2 条失败，确认汇总含类型/名称/期望/实际/取值路径且期望与实值都带类型（如 `'200' (str)`）。**`status_code` 不会误报「未知断言类型」**。
- 提取链路必跑：至少一条用例带 `extract`/`extract_global`（如 `extract_global: { token: [json, $.data.token, ""] }`）真实执行，确认 `parse_extract` 的 **3 元组** `(mode, path, default)` 被正确解包。

## ⚠️ 约束（保障功能不变）
1. 零代码边界：业务完全由 YAML 表达，不含 Python 测试代码。
2. 单 API 文件 + 业务组合复用（唯一模型）：跨接口关联用 `extract_global` + `${read_yaml(name)}`；差异用 `with`。
3. 仅 YAML：用例只支持 `.yaml`/`.yml`；YAML 内的 `json:` 指 HTTP 请求体类型，与用例文件格式无关。
4. 多类型软断言 + 链路硬停止：规则与错误格式以 `reference_contract.md` 为准。
5. 鉴权单点：Token/请求头注入只在 `common/request_client.py`（已由模板固化）。
6. 断言可追溯：`validate` 声明式写在 YAML 中；`status_code`/`status` 隐含 `resp.status_code` 的 equals。
7. 中文 UTF-8。
8. 配置分层：`config/config.yaml` 配 `base_url`/报告/`env`/`mail`；开关在 `pytest.ini`；失败重试交 `pytest-rerunfailures`；**环境变量覆盖仅在「非空」时生效，空串/未设置回落配置**。
9. **base_url 缺失即报错**：`config.yaml` 未配 `base_url`（且 `BASE_URL` 环境变量为空）则运行抛配置错误，不收集、不 skip，禁止无服务空跑。
10. 默认请求头单一来源：`data/share.yaml` 的 `default_headers` 为默认层；合并优先级 `default_headers < feature.headers < request/with.headers`；`Authorization` 仅无时注入。
11. 数据与结构分离：敏感值只进 `data/<env>.yaml`；其余常量进 `data/`。
12. 常见坑遵循 `reference_contract.md` 第六节：体类型/业务码字符串/404/token 鉴权/并行 loadscope；`equals` 对字符串↔数字数值宽容；`executor` 支持 `json`/`form`/`data`/`files` 四体。
13. 报告开关独立：`enable_allure_report`/`auto_open_report`/`enable_email_report` 环境变量可覆盖；重试不自行实现、`historyId` 聚合去重。
14. 多环境零改动：`--env dev/test/staging/prod` 或 `TEST_ENV` 选 `data/<env>.yaml`（优先级 `--env` > `TEST_ENV` > `config.yaml.env` > `test`）。
15. 邮件不阻断：缺 `smtp_host`/`receivers` 或发送异常仅 `logging.warning` 并返回 `False`，`smtp_password` 用 `MAIL_SMTP_PASSWORD` 注入。
16. **断言类型分派必须完整**：`_check` 覆盖全部类型**及别名**（`eq/ne/gt/lt/gte/lte/matches`）+ `status_code`/`status` 独立分支（actual 隐含 `resp.status_code`）。漏分派会落「未知断言类型」分支。
17. **`pytest.ini` 的 bool 型 ini 值禁止行内注释**：注释只能单独成行写在开关上方。

## ✅ 验证
1. `py_compile` 全过；`pytest --collect-only` 收集 `flows/` 为单个 Item（Item 名 = title），`apis/` 不直接收集。
2. 检索：发请求仅在 `request_client.py`。
3. 多类型断言验证：混合多类型并故意让两条失败，错误信息含类型/名称/期望/实际/取值路径，期望/实值带类型（`(str)`/`(int)`）。
4. 软断言验证：一个 API 内所有断言均执行（汇总含全部失败项）。
5. 链路硬停止验证：让某 API 断言失败，确认 ①日志 `步骤 i/n 失败，硬停止后续步骤 [name]` + 完整 `接口[名]/请求/响应/错误` 块；②后续步骤日志 `⏭️  API「x」已跳过：上游 API『y』执行失败，已停止执行本业务后续 API`；③`repr_failure` 只展示可读摘要（不附堆栈）；④Allure 失败详情附件含同一段 detail。
6. 复用验证：同一份 `apis/` 文件被多个 flow `include`；`with` 覆盖不影响其它引用。
7. 状态断言验证：`- status_code: { expected: 200 }` 在真实返回 200 时必须通过（无「未知断言类型」）。
8. 配置解析验证：`pytest --collect-only` 无 `invalid truth value` 报错（bool 开关无行内注释）。
9. 重试验证：故意让一个 case 失败，确认 `RERUN [n%]` 出现一次，最终仍失败；`report.json` 的 `total` 不含重试中间态。
10. Content-Type 驱动体编码验证：headers 写 `Content-Type: application/x-www-form-urlencoded`、body 用 `form:` → 走 `data=`；用 `json:` + JSON Content-Type → `json=`。

- [ ] 目录结构与树一致（由 scaffold.py 生成）
- [ ] `apis/` 单 API 文件可复用；`flows/` 用 `steps` 引用
- [ ] 收集只收集 `flows/`（展开多 Item），`apis/` 不直接收集
- [ ] 新增 YAML 即被收集为用例（无需改 Python）；`.gitignore` 已排除 logs/reports/allure-results/artifacts
- [ ] 失败用例在 `artifacts/` 留证并挂载 Allure；生成报告带 `history`（趋势）
