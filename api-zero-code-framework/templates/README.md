# 零代码 API 自动化框架

以「单个 API 一个 YAML 文件」为可复用单元，业务文件用 `steps` 引用多个单 API 组合成链路。**新增一个 YAML 文件即新增一条用例，无需写 Python。**

## 目录结构

```
engine/            # 零代码核心（执行引擎 + 收集器 + 报告/通知）
common/            # 配置/请求/上下文/数据/断言/脱敏
utils/            # 字典/提取/模板/脱敏 纯函数
testcases/
  apis/           # 单 API 定义库（可复用，不直接收集）
  flows/          # 业务编排（被收集为用例）
examples/         # 用例模板参考（your_api.yaml / your_flow.yaml，含 <...> 占位符，不收集）
config/config.yaml# 统一配置（base_url / 报告 / env / mail）
data/             # 测试数据（按环境切换，share ⊕ env 深合并）
scripts/          # 运行脚本（run_tests.py / runner.py）
conftest.py       # pytest 插件注册 + 会话级报告
pytest.ini        # 功能开关与并行/重试
.gitlab-ci.yml    # GitLab CI 示例
.github/workflows/api-tests.yml  # GitHub Actions 示例
```

## 快速开始

```bash
pip install -r requirements.txt
# 编辑 config/config.yaml，填写 base_url（被测服务地址，运行必需）
python scripts/run_tests.py --env test
```

## 如何添加测试用例

1. **定义单 API**：在 `testcases/apis/` 新建一个 `.yaml`，一个文件 = 一个可复用 API（以下用 `<...>` 占位符，替换成你的真实值）。

   ```yaml
   # testcases/apis/<api_name>.yaml
   name: <api_name>
   request:
     method: "<METHOD>"                 # 引用 data/share.yaml 的方法常量，如 "${POST}"
     url: /<resource>/<action>          # 相对路径；完整地址由 config.yaml 的 base_url 前缀拼接
     json:
       <field>: "${<constant>}"         # 值用 ${...} 引用 data/ 中的常量（敏感值放 data/<env>.yaml）
   extract_global:                      # 跨业务共享（下游用 ${<shared_var>} 取）
     <shared_var>: [json, $.data.<field>, ""]
   validate:
     - equals:       { name: <断言说明>, actual: $.code, expected: "${expect.success_code}" }
     - status_code:  { name: HTTP状态, expected: 200 }
   ```

2. **编排业务**：在 `testcases/flows/` 新建一个 `.yaml`，`steps` 引用上面的 API；`with` 覆盖本次调用以衍生正向/反向用例。

   ```yaml
   # testcases/flows/<flow_title>.yaml
   title: <flow_title>
   steps:
     - include: apis/<api_name>.yaml
     - include: apis/<api_other>.yaml
     - include: apis/<api_name>.yaml
       with:
         json: { <field>: <value> }                 # 覆盖请求体
         validate:                                   # 覆盖断言（正向/反向复用同一定义）
           - equals: { name: <断言说明>, actual: $.code, expected: "<code>" }
   ```

- 复用：同一份 `apis/` 文件可被多个 `flows/` `include`；`flows/` 也可被另一份 `flows/` `include`（嵌套业务，顶部加 `component: true` 跳过直接收集）。
- `with` 兼容「顶层直平铺」与「`with.request` 嵌套」两种写法；可覆盖 `request` 及 `validate`/`extract`/`extract_global`。
- 数据外部化：method/url/预期码/账号密码等用 `${...}` 引用 `data/` 中的常量；敏感值只放 `data/<env>.yaml`。

### 参考示例（examples/ 模板）

| 位置 | 作用 | 是否收集/运行 |
| --- | --- | --- |
| `examples/your_api.yaml` | 单 API 写法参考（骨架，含 `<...>` 占位符） | 否 |
| `examples/your_flow.yaml` | 业务编排写法参考（骨架，含 `<...>` 占位符） | 否 |
| `testcases/apis/*.yaml` | 你写的**真实**单 API（可复用，不被直接收集） | 否（由 flows 引用） |
| `testcases/flows/*.yaml` | 你写的**真实**业务用例（新增一个文件 = 新增一条用例） | 是（自动收集） |

> 写用例时，把 `examples/` 下的参考文件**复制**到 `testcases/apis/` 或 `testcases/flows/` 并替换 `<...>` 占位符即可；`examples/` 本身只是参考，放哪都不会被当成用例执行。详见 `data/share.yaml` 常量定义。

## 断言类型

`validate` 支持：`equals`/`not_equals`/`greater_than`(`gt`)/`less_than`(`lt`)/`greater_or_equal`(`gte`)/`less_or_equal`(`lte`)/`contains`/`not_contains`/`in`/`not_in`/`length`/`min_length`/`max_length`/`type`/`regex`(`matches`)/`exists`/`not_exists`/`schema`/`status_code`(`status`)。一个 API 内全部执行后汇总（软断言）；业务内任一失败则硬停止后续步骤。

## CI/CD

```bash
# 本地 / CI 统一入口
python scripts/run_tests.py --env test           # 默认环境 test
python scripts/run_tests.py --env prod --email on   # 需注入 MAIL_SMTP_PASSWORD
python scripts/run_tests.py --env dev -k <keyword> -n auto   # 透传 pytest 参数（含并行）
```

- 多环境零改动：`--env dev/test/staging/prod` 或环境变量 `TEST_ENV` 选择 `data/<env>.yaml`（优先级 `--env` > `TEST_ENV` > `config.yaml.env` > `test`）。
- 失败重试由 `pytest-rerunfailures` 负责（默认各 1 次），按 `historyId` 聚合去重。
- 流水线产物：`allure-results/`、`reports/`（含 `report.json` / `allure-report`）、`reports/junit.xml`。
- Allure 报告前置：需 Java(JRE/JDK 8+) 与 `allure-commandline`（缺失时给出安装指引，不静默失败）。
