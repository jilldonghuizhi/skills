# API 框架 · 写用例契约（语义真相源，按需查阅）

本文是**编写 YAML 用例**时的语义参考（字段、断言、变量、坑）。**框架源码已在 `templates/` 中固化，搭骨架由 `scaffold.py` 完成，勿再逐字生成 Python。**

## 一、YAML 文件结构（仅 YAML）

### ① 单 API 定义文件（`testcases/apis/`，可复用组件，不直接收集）
一个文件 = 一个 API，自包含 `request` + `extract`/`extract_global` + `validate`。

```yaml
# testcases/apis/your_api.yaml —— 单 API 模板
name: <api_name>
request:
  method: <http_method>              # 引用 data/share.yaml 的方法常量（勿硬编码 post/get）
  url: /<resource>/<action>          # 相对路径；完整地址由 config.yaml 的 base_url 前缀拼接
  json: { <field>: <value> }         # 服务端要 JSON 时用 json:；要表单用 form:
extract_global:                     # 跨业务共享（下游用 ${<shared_var>}；跨 case 用 ${read_yaml(name)}）
  <shared_var>: [json, $.data.<field>, <default>]
validate:                           # 多类型软断言（失败汇总）
  - equals:      { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }
  - status_code: { name: <断言说明>, expected: 200 }
```

### ② 业务编排文件（`testcases/flows/`，一个文件 = 一个 case）
`steps` 顺序引用多个单 API 文件（或嵌套另一份 `flows/`）；每个 step 可附加 `with`（覆盖本次调用的 request 及 validate/extract）。

```yaml
# testcases/flows/your_flow.yaml —— 业务模板
title: <flow_title>
steps:                              # 业务 = 多个单 API / 子业务组合（顺序执行）
  - include: apis/your_api.yaml
  - include: apis/your_api.yaml
    with:
      json: { <field>: <value> }               # 覆盖请求体
      validate:                     # 覆盖断言（正向/反向复用同一定义）
        - not_equals: { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }
  # - include: flows/your_sub_flow.yaml    # 嵌套业务，递归展开为 父业务::子业务::API
```

- `steps` 每项：字符串即 `include` 路径；或 dict `{ include, name?, with? }`。`include` 可指向 `apis/` 单 API，也可指向另一份 `flows/`（嵌套业务，递归展开）。
- `include` 解析优先级：业务文件目录 `apis/`/`flows/` → 全局 `testcases/apis/`/`testcases/flows/` → 业务文件相对路径。
- `with`：深度合并进被引用文件的 spec——覆盖 `request`（`json`/`params`/`headers`，不覆盖 `method`/`url`）**及** `validate`/`extract`/`extract_global`。兼容「顶层直平铺」与「`with.request` 嵌套」两种写法。

## 二、字段语义

| 位置 | 字段 | 说明 |
| --- | --- | --- |
| 单 API 顶层 | `name` | API 名（Item 名组成部分） |
| 单 API 顶层 | `request` | 必填：method/url/path/params/query/headers + 请求体（`json`/`form`/`data`/`files` 四选一） |
| 单 API 顶层 | `extract` | 提取规则（本业务可见） |
| 单 API 顶层 | `extract_global` | 提取规则（跨业务全局共享） |
| 单 API 顶层 | `validate` | 断言列表（多类型 + 软断言） |
| 业务顶层 | `feature`/`story`/`title` | 业务级元信息（title 标识业务） |
| 业务顶层 | `steps` | 必填：引用多个单 API 文件（列表） |
| `steps[].include` | 被引用的单 API（`apis/`）或另一份业务（`flows/`，嵌套）路径 |
| `steps[].name` | 可选，覆盖该次调用 API 显示名 |
| `steps[].with` | 可选，深度合并进 spec：覆盖 `request` 及 `validate`/`extract`/`extract_global` |
| `extract`/`extract_global` | `key: $.data.code`（JSONPath）或 `key: [json, $.code, 0]`（带默认值，字段缺失取默认） |

## 三、断言（validate · 多类型 · 软断言）

`validate` 是**断言列表**，每个元素唯一键为**断言类型**，值为参数：

```yaml
validate:
  - equals:        { name: <说明>, actual: $.data.<field>, expected: <v> }
  - status_code:   { name: <说明>, expected: 200 }            # actual 隐含为响应状态码
  - greater_than:  { name: <说明>, actual: $.data.<field>, expected: <v> }
  - not_equals:    { name: <说明>, actual: $.data.<field>, expected: <v> }
  - contains:      { name: <说明>, actual: $.data.<field>, expected: <v> }
  - not_contains:  { name: <说明>, actual: $.data.<field>, expected: <v> }
  - in:            { name: <说明>, actual: $.data.<field>, expected: [<v1>, <v2>] }
  - not_in:        { name: <说明>, actual: $.data.<field>, expected: [<v1>] }
  - length:        { name: <说明>, actual: $.data.<field>, expected: <v> }
  - min_length:    { name: <说明>, actual: $.data.<field>, expected: <v> }
  - max_length:    { name: <说明>, actual: $.data.<field>, expected: <v> }
  - type:          { name: <说明>, actual: $.data.<field>, expected: <type> }
  - regex:         { name: <说明>, actual: $.data.<field>, pattern: "^1[3-9]\\d{9}$" }
  - exists:        { name: <说明>, actual: $.data.<field> }         # 存在且非空
  - not_exists:    { name: <说明>, actual: $.data.<field> }         # 不存在或为空
  - schema:        { name: <说明>, actual: $, schema: { type: object, required: [<f1>, <f2>] } }
```
> 单个断言也可直接写成一个 dict（非列表），引擎视为单元素列表。`name` 写清「校验什么」。

### actual 表达式文法
| 写法 | 含义 |
| --- | --- |
| `status_code` | 响应状态码 |
| `$.x` | 对响应 JSON 取 JSONPath |
| `${read_yaml(name)}` / `${name}` | `extract`/`extract_global` 变量（保持原始类型） |
| `${env.X}` / `${context.X}` | 环境变量 / 上下文变量 |
| 字面量 | 数字 / 字符串 / 布尔 / 列表 |

### 断言类型一览
| 类型 | 含义 | 参数 |
| --- | --- | --- |
| `equals` | 宽松相等（`"200"`==`200`，其余 `==`） | `actual`,`expected` |
| `not_equals` | 不相等 | `actual`,`expected` |
| `greater_than`/`gt` | 大于 | `actual`,`expected` |
| `less_than`/`lt` | 小于 | `actual`,`expected` |
| `greater_or_equal`/`gte` | ≥ | `actual`,`expected` |
| `less_or_equal`/`lte` | ≤ | `actual`,`expected` |
| `contains` | 包含（str⊇sub / item∈list / key∈dict） | `actual`,`expected` |
| `not_contains` | 不包含 | `actual`,`expected` |
| `in` | 属于集合 | `actual`,`expected`(列表) |
| `not_in` | 不属于集合 | `actual`,`expected`(列表) |
| `length` | 长度等于 | `actual`,`expected` |
| `min_length` | 长度 ≥ | `actual`,`expected` |
| `max_length` | 长度 ≤ | `actual`,`expected` |
| `type` | 类型检查 | `actual`,`expected`(`str`/`int`/`float`/`bool`/`list`/`dict`/`null`) |
| `regex`/`matches` | 正则匹配 | `actual`,`pattern` |
| `exists` | 存在且非空 | `actual` |
| `not_exists` | 不存在或为空 | `actual` |
| `schema` | JSON Schema 校验 | `actual`,`schema` |
| `status_code`/`status` | 状态码等于 | `expected`（actual 隐含） |

> **别名必须显式分派**：`status_code`/`status`=「actual 隐含 `resp.status_code` 的 equals」；`eq/ne/gt/lt/gte/lte/matches` 为别名。漏分派会命中「未知断言类型」兜底，表现为「HTTP 200 却断言失败」。

### 软断言（API 内）
一个 API 内**所有断言都会执行**，全部跑完后若有失败，抛出**汇总** `AssertionError`，逐条列出类型、名称、期望值、实际值、取值路径。错误信息格式：
```
❌ 业务「<flow_title>」· API「<api_name>」断言失败：共 N 项未通过
  1. [equals · <说明>] 期望 == '<expected>' (str) | 实际 '<actual>' (str)  （取值: 响应 $.data.<field>）
```

### 业务链路硬停止（API 间）⚠️
同一业务（flow）内，若某 API 失败（断言汇总失败 / 请求异常），**立即停止后续 API**，后续标记为 `skipped` 并指向失败上游。日志输出 `步骤 i/n 失败，硬停止后续步骤 [name]` + 完整 `接口[名]/请求/响应/错误` 块；后续步骤输出 `⏭️  API「x」已跳过：上游 API『y』执行失败，已停止执行本业务后续 API`。

## 四、模板与变量（utils/templating.py）

`resolve(value, ctx)` 递归渲染 `${...}`：`${var}` / `${env.X}` / `${context.X}` / `${read_yaml(X)}`（最后者与 `${X}` 等价）。变量查找顺序：`ctx.data（运行时 extract/extract_global）` → 常量命名空间（`data/` 环境合并后）→ 未命中保留原样。
- **整值替换**：字段整体即 `${x}` 时返回解析出的对象（dict/list/标量），而非字符串拼接。
- **引号注意**：`${...}` 出现在行内 flow mapping（`{ ... }`）的值中时必须加引号（如 `expected: "${expect.success_code}"`），否则 YAML 会把内部 `{` 当作嵌套 flow mapping 解析失败。
- **递归渲染**：`value` 为 dict/list 时递归其每个元素，使 `headers`/`json` 内部值也能用 `${...}`。
- `method` 字段同样经 `resolve` 解析（见第九节）。

## 五、数据复用（常量 / 环境 Profile）

数据与结构分离：**用例 YAML 只写结构/逻辑，具体值用 `${...}` 引用 `data/` 中的常量**。
- **具体值默认全部外部化到 `data/`**：HTTP method、URL、请求头、请求体、预期业务码/状态码等**跨环境一致**的值在 `data/share.yaml` 定义为常量；**账号密码/token 等环境专属敏感值不放 `share.yaml`，改放 `data/<env>.yaml`**，由 `env` 深合并覆盖。用例通过 `${...}` 引用；**结构与逻辑**（`steps` 编排、`validate` 的断言类型与 `actual` 取值路径、`extract` 规则）留在用例文件。
- `data/share.yaml` 统一定义方法常量 `{ GET: get, POST: post, ... }`，API 里 `method: "${POST}"`；预期码 `expect: { success_code: "200" }`，断言 `expected: "${expect.success_code}"`（注意加引号）。
- 默认头由 `data/share.yaml` 的 `default_headers` 提供（executor 注入为默认层；合并优先级 `default_headers < feature.headers < request/with.headers`）。鉴权单点（`Authorization`）仅在尚无时注入，不覆盖既有值。
- 加载与合并：启动加载 `data/share.yaml`，按 `env` 深合并 `data/<env>.yaml`，得到当前环境常量命名空间，作为 `resolve` 基础层。
- 优先级（低 → 高）：`常量(环境合并后) < ctx 运行时(extract_global) < with 字段级覆盖`。

## 六、常见坑与规避（生成用例/排障必读）

1. **请求体类型**：`json:`→JSON；`form:`/`data:`→x-www-form-urlencoded；`files:`→multipart。**用错类型服务端常返回业务码 500（HTTP 仍 200）**。登录/提交类接口若返回"未知异常"，优先怀疑体类型，用 Apifox/DevTools 看该接口收 JSON 还是表单，再换 `json:`↔`form:`。
2. **业务码常是字符串**：很多服务端成功码是 `"200"`（甚至 `"0"`）。`equals` 已做数值宽容，但 `type`/`length` 类断言仍看真实类型。预期码统一走 `expect.success_code`（`data/share.yaml` 定义为字符串），flow 映射内写 `expected: "${expect.success_code}"` **必须加引号**。
3. **404/非 JSON 响应**：路径写错 → 404 返回 HTML，`resp.json` 为 `None`，`$.code` 取到 `None`、断言报「实际 None」。看状态码是否 4xx/5xx、URL 与方法是否一致；框架会对「非 JSON 却按 JSONPath 取值」给出明确提示。405=方法不对；404=路径不存在，二者都与 token 无关。
4. **Token 鉴权**：三种常见——`Authorization: Bearer <token>`；`Authorization: <裸token>`（不加 Bearer）；token 作为查询参数/表单字段。**同一后端只用一种**。以 Apifox/DevTools 能跑通的请求为准：看 token 放 header 还是 body/param、加不加 Bearer，YAML 里 1:1 复刻。登录接口用 `extract_global` 把 token 写入全局，下游用 `${token}` 引用。
5. **并行（xdist）**：必须 `--dist loadscope`（已固化进 `pytest.ini` 的 `addopts`），否则同 flow 步骤拆到不同进程，变量丢失、硬停止失效。`extract_global` 是进程级、跨 worker 不互通；跨 flow 依赖全局变量的链路要么合并进同一 flow，要么串行跑。
6. **Allure 报告**：结果目录走 `pytest.ini` 的 `--alluredir=allure-results`；生成+打开走 `conftest`（`enable_allure_report` / `auto_open_report` 开关独立）。前置依赖 Java(JRE/JDK 8+) + `allure-commandline`，缺失时 `generate_report` 返回非 0 并打印跨平台安装指引，不静默失败。`environment.properties` 键名**不能含空格**。
7. **`pytest.ini` 的 bool 开关不能写行内注释** ⚠️：现象 `ValueError: invalid truth value 'true   # ...'`，整会话连 `--collect-only` 都失败。原因 `enable_allure_report`/`auto_open_report`/`enable_email_report` 注册为 `type="bool"`，pytest 把等号后整行当值解析。规避：注释单独成行写在开关上方，只写 `true`/`false`。
8. **断言类型别名漏分派 →「HTTP 200 却断言失败」**：现象 `- status_code: { expected: 200 }` 在真实 200 时仍失败，错误 `未知断言类型 'status_code'`。规避：`_check` 入口先做别名归一化（`status_code`/`status`→equals；`eq/ne/gt/lt/gte/lte/matches`→对应全名）。生成后**必须跑一次只含 `status_code` 断言的用例**确认通过。

## 七、功能开关与重试（速查）

- 开关集中在 `pytest.ini`，由 `conftest.py` 读取，环境变量优先覆盖：`enable_allure_report`(ENABLE_ALLURE_REPORT) / `auto_open_report`(AUTO_OPEN_REPORT) / `enable_email_report`(ENABLE_EMAIL_REPORT)。写法见第六节-7。
- 失败重试交 `pytest-rerunfailures`（`pytest.ini` 的 `--reruns 1 --reruns-delay 1`），按 `historyId` 去重，不增加用例计数。
- 多环境：`--env dev/prod` 或 `TEST_ENV` 选择 `data/<env>.yaml`（优先级 `--env` > `TEST_ENV` > `config.yaml.env` > `dev`）。
- 邮件：`enable_email_report=true` + `config.yaml` 的 `mail:` 节；`smtp_password` 用 `MAIL_SMTP_PASSWORD` 注入，缺配置/异常仅告警不阻断。
