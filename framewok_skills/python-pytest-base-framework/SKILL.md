---
name: python-pytest-base-framework
description: Python + pytest 通用自动化测试框架生成器（二次开发底座，最终产出外部可用的 base_framework Python 包）。提供日志、Allure 报告、YAML 配置与邮件能力，供 Web/App/API 等测试框架复用。支持按需生成 GitHub Actions CI、GitLab CI 或 Jenkins 流水线，以及用户明确要求时的受控 Python 包发布 CD。用户要求 pytest 测试底座、报告封装或 CI/CD 时触发；不注入真实业务逻辑或凭据。
---

## 🎯 角色与目标

你是一位高级测试开发工程师，精通 Python 与 pytest 生态。你的任务是：当用户要求生成 pytest 二次开发框架时，在指定工作目录下一次性生成一套**与具体被测对象解耦、可对外复用**的二次框架包。底座只提供通用能力：**日志（logger）、报告生成（Allure HTML / 邮件）、YAML 配置、汇总与报告生成工具**，并**打包成可 `pip install -e .` 的外部包（默认包名 `base_framework`）**，让 Web / App / 接口等方向的二次框架只需要 `import base_framework` 即可获得日志、报告、邮件、报告生成能力，而**不用内嵌或复制底座代码**。

> **重要定位**：本底座**不区分 Web / App / 接口 / 其他方向**。它只交付一个可安装的二次框架包。Web/App/接口等方向通过 `pip install -e <该包>` + `import base_framework.*` 来复用日志 / 配置 / 汇报 / 邮件，不修改底座包核心。

**核心目标**：交付**外部可用的二次框架包**（可 `pip install -e .` 安装），包含 logger / config / report / email / report_generator，并说明各方向二次框架如何消费；CI/CD 仅在用户要求时按需生成。

## 📋 前置条件与输入

1. **触发条件**：当用户的请求包含以下任一语义时触发本 skill：
   - "生成 pytest 框架 / 通用测试框架 / 二次开发框架"
   - "把底座封装成可 import 的包 / 二次开发框架包"
   - "日志 + 报告封装 / 测试报告生成"
   - "提供一个能直接 import 的通用底座（logger/报告/配置/邮件）"
   - "为 pytest 底座添加 CI/CD、GitHub Actions、GitLab CI 或 Jenkins 流水线"
2. **根目录变量 `${PROJ_DIR}`**：目标工程根目录。取值优先级：
   1. **用户显式指定**的目标目录（如消息中给出目录名 / 路径）
   2. **默认值**：`python_pytest_base_framework`
   - 变量为**相对路径**，以当前工作目录为锚；下文所有文件路径、目录树、命令的根都以 `${PROJ_DIR}/` 为基准，**禁止写死其他绝对路径**。
3. **环境依赖**：Python ≥ 3.9，可 `pip install -e .` 安装；Allure 报告生成依赖系统 `allure` 命令（需 JDK 8+，本机可选）。
4. **权限要求**：目标目录写权限、`pip install -e` 安装权限、可选访问外部 SMTP（仅运行时）。
5. **必填输入（缺失须主动追问，禁止猜测）**：目标工程目录（用户指定或默认 `python_pytest_base_framework`）；是否需要 CI/CD（默认不生成；指定平台则沿用仓库既有平台或默认 GitHub Actions）。
6. **知识基线**：熟悉 pytest 插件机制、打包（`pyproject.toml` + setuptools）、Allure 结果结构、`pytest-xdist` 并行、SMTP / HTML 邮件模板。

## 🚶 标准化工作流

### Step 1：确认目标目录
- 解析 `${PROJ_DIR}`——用户指定则用之，否则默认 `python_pytest_base_framework`（相对当前工作目录）。

### Step 2：创建目录结构（幂等）
- 基于 `${PROJ_DIR}` 创建 `pyproject.toml`、`base_framework/`、`README.md`、`requirements.txt`。**目录已存在则不重建**，已存在文件**不覆盖**，只补齐缺失项。

### Step 3：按规范逐文件写入（仅写缺失）

**框架结构（必须严格遵守）——对外可用的二次框架包**：

生成的目录结构必须如下，每个文件真实写入、可运行。**不含任何浏览器 / App / 接口驱动代码**；`base_framework/` 是一个可安装的 Python 包。用户要求 CI/CD 时，才在此骨架上追加对应工作流和隔离的包测试：

```
${PROJ_DIR}/                          # 二次框架包工程根
├── pyproject.toml                    # 打包配置：包名 base_framework；`pip install -e .` 后全局可 import
├── README.md                         # 包说明、安装与对外 import API 用法
├── requirements.txt                  # 依赖清单（pytest / allure-pytest / PyYAML 等）
└── base_framework/                   # 对外 API 包（核心，可被任何工程 import）
    ├── __init__.py                   # 导出公共 API（get_logger / ConfigReader / build_summary / ...）
    ├── logger.py                     # 日志封装（控制台 + 文件，按天轮转，保留 30 天）
    ├── config_reader.py              # YAML 配置读取（支持环境变量覆盖 / 自定义路径）
    ├── report.py                     # 报告工具：解析 allure 结果、生成机器可读汇总
    ├── email_sender.py               # SMTP 邮件发送（报告/失败通知，附 HTML 模板）
    └── report_generator.py           # 生成 Allure HTML、保留 Trend、跨平台定位 allure
```

> 说明：二次框架包**只交付可复用的能力包**，不内置用例、不内置工程骨架（是否有往工程内复制由各方向二次框架决定）。包名默认 `base_framework`，可在 `pyproject.toml` 中调整。

**用户明确要求 CI/CD 时追加**：

```
${PROJ_DIR}/
├── .github/workflows/ci.yml           # GitHub Actions CI（仅在选用此平台时生成）
├── tests/
│   ├── test_config_reader.py          # 配置加载和环境变量覆盖
│   └── test_report.py                 # 汇总与 report.json 输出
└── .gitignore                         # 忽略测试/构建/报告产物与本地凭据
```

如果仓库已经使用 GitLab CI 或 Jenkins，应复用其平台并生成 `.gitlab-ci.yml` 或 `Jenkinsfile`，不要另加并行平台配置。CD/包发布默认关闭，只有用户明确要求发布时才加入受控发布工作流。

**pyproject.toml（打包配置，关键）**：

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "base_framework"
version = "0.1.0"
description = "传输无关的 pytest 二次开发底座包：logger/report/email/config"
requires-python = ">=3.9"
dependencies = [
    "pytest>=7.4", "allure-pytest>=2.13", "PyYAML>=6.0", "python-dotenv>=1.0",
    "pytest-rerunfailures>=12.0", "pytest-xdist>=3.5",
]

[tool.setuptools.packages.find]
include = ["base_framework*"]
```

**base_framework/__init__.py（公共 API 契约）**：

```python
"""base_framework：可被任何 pytest 二次框架 import 的通用底座包。"""

from .logger import get_logger
from .config_reader import ConfigReader, get_config
from .report import (
    build_summary,
    write_json_report,
    finalize_report_session,
    reset_allure_dir,
    attach_failure_artifact,
)
from .email_sender import EmailSender
from .report_generator import generate_report

__all__ = [
    "get_logger",
    "ConfigReader",
    "get_config",
    "build_summary",
    "write_json_report",
    "finalize_report_session",
    "reset_allure_dir",
    "attach_failure_artifact",
    "EmailSender",
    "generate_report",
]
```

**核心模块编写规范**：

- **3.1 requirements.txt 依赖**：
  ```
  pytest>=7.4
  pytest-rerunfailures>=12.0
  pytest-xdist>=3.5
  allure-pytest>=2.13
  PyYAML>=6.0
  python-dotenv>=1.0
  ```
  > 默认标准库 `logging`；如需 `loguru` 再行替换。日志着色可用 `colorlog` 或 ANSI。
  >
  > **依赖双清单同步**：`pyproject.toml` 的 `[project].dependencies` 与 `requirements.txt` 是同一依赖清单的两份载体，新增 / 调整依赖时**必须两处同步修改**，防止 `pip install -e .` 与 `pip install -r requirements.txt` 装出不一致的环境。

- **3.2 config_reader.py 配置读取**：
  - `ConfigReader(config_path=None)`：加载 YAML，提供 `get(key, default)` / `get_section(sec)` / `to_dict()`。
  - 顶层字段支持环境变量覆盖（布尔 / 整数 / 列表 / 字符串分别解析）。
  - **节内子键覆盖**：敏感项（如 `EMAIL_AUTH_CODE`、`EMAIL_SENDER`）经 `{节名}_{子键}` 环境变量注入，YAML 不落盘明文；列表用 `[a,b]` 形式（如 `EMAIL_RECEIVERS=[a@x.com,b@x.com]`）。
  - `get_config(config_path=None)` 便利函数：`config_path` 缺省时取环境变量 `BASE_FRAMEWORK_CONFIG`，再回落当前工作目录 `config/config.yaml`。
  - **给消费方用**：Web/App/接口 自己提供 config.yaml（含自身方向段 + 顶层 `report/email`），通过 `ConfigReader("config/config.yaml")` 喂入，复用底座解析能力，不重复实现 YAML 解析。

- **3.3 logger.py 日志模块**：
  - 标准库 `logging`，输出到控制台与文件。
  - 文件按日期轮转（`TimedRotatingFileHandler`），保留 30 天。
  - 格式 `时间 | 级别 | 文件名:行号 | 消息`。
  - 提供 `get_logger(name, level=None)` 工厂函数；控制台按级别着色。
  - **非 UTF-8 控制台兜底（Windows GBK）**：装配 handler 前对 `sys.stdout`/`sys.stderr` 执行幂等的 `reconfigure(errors="replace")`（仅当流编码非 UTF-8 且流对象支持 reconfigure；失败吞异常不阻断）。否则中文日志在 Windows 默认 GBK 控制台触发 `UnicodeEncodeError`（Logging error 噪音甚至丢日志）。
  - 日志文件默认写当前工作目录 `logs/`。

- **3.4 report.py 报告工具（与具体驱动无关）**：
  - `build_summary(allure_dir) -> dict`：解析 allure-results 下 json，聚合 `total / passed / failed / skipped / duration / failures[] / cases[]`。
  - **只统计 `*-result.json`**：`*-container.json`（fixture/setup/teardown 容器）与 executor/categories/history 等非用例文件一律不计入 total，避免统计失真。
  - `failures[]` 每项含 `name`、`error`、`attachments`（截图 / 报文路径等）；`source` 须为**相对当前工作目录的完整路径**（如 `allure-results/xxx.png`），便于邮件 / 外部程序直接定位真实文件。
  - `cases[]` 全量用例：含 `name`（`函数名[参数]` 格式）、`status`、`duration`、`error`（仅失败）、`attachments`（仅失败），供邮件「用例明细」表渲染全部用例。
  - `env{}`：由 `finalize_report_session` 合并写入，含 `os`（缺省 `platform.system() + release`）、方向注入的 `target/app/device/report` 等，供邮件「环境信息」表。
  - `write_json_report(summary, out_path)`：写机器可读 `report.json`，供外部程序 / 邮件消费。

- **3.5 email_sender.py 邮件发送**：
  - 标准库 `smtplib` + `email.mime`，支持 SSL/STARTTLS，无额外第三方依赖。
  - `EmailSender().send(subject, html_body, attachments=None)`、`send_report(summary, attachments=[])`。
  - **收件人回退**：`receivers` 留空时默认发给发件人自己（`[sender]`）。
  - **截图内联**：失败截图（png/jpg/gif/webp/bmp）以 `cid:` 内联嵌入邮件正文（模板 `<img src="cid:文件名">` 匹配）。
  - **附件策略**：`send_report` 只附 trace（`.zip`），不附日志文件；trace 文件名须与用例名关联（如 `trace_test_login[登录失败].zip`）。
  - 主题 `{prefix} 通过率{rate}% | {date} {time}`；发送失败吞异常并 `logger.error`，不阻断流程。

  **截图内联关键实现要点（miss 会导致邮件中截图空白）：**
  1. **source 路径前缀**：`build_summary` 产出的 `attachments[].source` 是 **allure 结果目录内的文件名**（如 `a5baf188-...-attachment.png`），**不含目录前缀**。收集内联图片时必须拼接 `allure_dir`（默认 `allure-results/`）才能找到真实文件：`Path(allure_dir) / source`。直接 `Path(source).exists()` 会在当前工作目录下查找，返回 `False`，导致截图不入 `inline_images`，邮件中截图列为「—」。
  2. **cid 匹配**：`inline_images` 的 key 用**纯文件名**（`Path(source).name`），HTML 模板中 `<img src="cid:文件名">` 的 cid 也用纯文件名，两者必须一致。
  3. **收集来源**：从 `summary["failures"]` 和 `summary["cases"]` 的 attachments 中都要收集图片（failures 用于附件打包，cases 用于表格渲染），确保 case 表中每行都能匹配到 cid。
  4. **trace zip 同理**：`_make_trace_zip` 打包 trace 时，`source` 同样需要拼接 `allure_dir` 前缀才能读到文件。

  **HTML 邮件模板排版要求：**
  - 三段式结构：**环境信息表**（测试环境/被测应用/设备型号/系统版本/Allure报告）→ **统计条**（用例总数/通过/失败/异常/通过率/耗时）→ **用例明细表**（用例名称/状态/耗时/错误信息/截图）。
  - **统计条**：用独立行列出各项指标（总数/通过/失败/异常/通过率），耗时单列一行，**不要把 10 个数字挤在一行**；统计条与环境信息表不重复展示耗时。
  - **表格列宽控制**：用例明细表必须设 `table-layout:fixed; width:100%`，否则 `max-width`/`width` 在 `<td>` 上不生效，列宽会随内容撑开。列宽比例：用例名称 25%、状态 6%、耗时 8%、错误信息 40%、截图 21%。
  - 截图 `width=120px` 等比缩小；图片以内联 `cid:文件名` 嵌入正文。
  - **斑马纹**：用例明细表奇偶行交替背景色（`#ffffff` / `#f6f8fa`），提升可读性。
  - 单元格 padding 紧凑（`2px 8px`），设备型号含品牌（如 `Chromium 149.0.7827.55`）。
  - 状态列使用语义色：通过 `#1a7f37`、失败 `#d1242f`、异常 `#bf8700`。
  - 用例明细展示全部用例（含通过用例，无截图时截图列显示「—」）。
  - **错误信息列**：失败用例必须展示完整断言错误信息（`statusMessage`），不截断、不省略；设 `word-break:break-all; font-size:12px` 防止长错误撑开表格。
  - **附件策略**：邮件附件只附 trace（`.zip`），不附日志文件；trace 文件名须与用例名关联。

- **3.6 report_generator.py 报告生成（外部可调用）**：
  - `generate_report(open_report=False) -> int`：生成 Allure HTML 到 `reports/allure-report`；返回 0 成功、非 0 失败（CLI 缺失 / 生成失败均如实返回非 0，不得静默吞掉）。
  - 保留 Trend：生成前把 `reports/allure-report/history` 复制进 `allure-results/history`。
  - 补齐 `allure-results/executor.json`、`categories.json`。
  - **allure CLI 定位回退链（依次尝试，逐级回退）**：
    1. `shutil.which("allure")`
    2. 环境变量 `ALLURE_BIN` / `ALLURE_CMDLINE` 指定的可执行文件路径
    3. npm 全局 `allure-commandline`（Windows 下优先取 `allure.cmd`；无扩展名 `.js` 用 `node` 执行，非 exe/cmd/bat 加 `node` 前缀）
    4. 局部安装的 `node_modules/allure-commandline/bin/allure`（依次查当前工作目录 `./node_modules`、`~/.allure-cli/node_modules` 等常见工具目录）
  - **CLI 缺失必须给出可操作的安装指引**：`logger.warning` 写明前置条件（JDK 8+）与安装命令（`npm install -g allure-commandline`，或官网下载 zip 解压后加入 PATH/设 `ALLURE_BIN`），并返回非 0。只说「无法生成报告」不说怎么装是反模式。
  - **打开报告禁止 `file://` 直开**：Allure HTML 报告是 SPA，靠 fetch 加载 `data/` 下 JSON，`file://` 协议被多数浏览器拦截，结果是一片空白页面。`open_report=True` 时优先 `allure open <report_dir>`（CLI 自带 HTTP 服务器，正确加载）；无 CLI 回退 `webbrowser.open(file://...)` 时必须 `logger.warning` 提示数据可能加载不出来，或起临时 `http.server` 再打开。
  - 中文路径规避：`cwd=ROOT_DIR` 下用相对路径传参，避免中文绝对路径经 ANSI 进 Java 乱码。

- **3.7 并行执行（pytest-xdist）—— 底座必须提供的并行安全装配**：
  底座把「报告汇总 / 邮件 / 自动开报告」收敛为**一个并行安全收尾函数**，供各方向二次框架在 `pytest_sessionfinish` 直接调用，从而**开箱即得并行执行**：
  ```python
  def finalize_report_session(session, allure_dir="allure-results",
                              report_out="reports/report.json",
                              auto_open=None, email_enabled=None,
                              env=None) -> dict | None:
      """pytest_sessionfinish 专用：一次走完 汇总->report.json->Allure->邮件。
      并行安全：xdist 下每个 worker 都会触发本 hook，内部以
      `getattr(session.config, "workerinput", None)` 判空，只在控制进程执行一次，
      避免每个 worker 各写一份 report.json / 各发一次邮件。
      env：方向层注入环境信息（target/app/device/report），os 缺省自动取平台版本，
      合并进 summary["env"] 供邮件「环境信息」表渲染。
      """
  ```
  **并行执行必须满足的约定：**
  1. **worker 识别**：`workerinput = getattr(session.config, "workerinput", None)`。xdist 并行（`-n N`）时，worker 进程带 `workerinput`；控制进程（或串行）没有。收尾时 `workerinput is not None` ⇒ 直接跳过（`return None`）。
  2. **仅控制进程收尾**：报告汇总 / `generate_report(open_report=True)` / `send_report` 只在控制进程执行一次。
  3. **`--collect-only` 守卫**：`session.config.option.collectonly` 为真时跳过收尾。
  4. **allure 结果合并**：运行 `-n N --alluredir=allure-results`，各 worker 的 allure 结果由 allure-pytest 自动合并进目标目录，收尾 `build_summary` 读到的是合并后全集。
  5. **并发资源**：各方向二次框架的 session 级 fixture（如浏览器 / 客户端）在 xdist 下按 worker 各自创建，天然并行；失败截图按 `failure_{nodeid}` 命名保证并发写不冲突。

  **runner.py（方向层）并行契约：** 各方向 runner 的 `parse_args` 增加 `--workers/-n`，运行时追加到 `pytest.main` 参数 `-n <N>`（N>0 时），实现一行并行。

- **3.8 运行前清理 allure-results（避免跨运行统计污染）**：
  多次运行会把旧的 result.json 累积在 `allure-results/`，导致 `build_summary` 读到跨运行残留、`report.json` 的 total/failed 失真。底座必须提供一个**并行安全的运行前清理函数**：
  ```python
  def reset_allure_dir(session=None, allure_dir="allure-results") -> None:
      """pytest_sessionstart 专用：清空 allure 结果目录，保证本次统计只含本轮用例。
      并行安全：传入 session 时，xdist 下除控制进程外的 worker 直接跳过
      （避免多进程竞争删除）；
      collect-only 守卫：--collect-only 不产生新结果，清空只会白丢上一轮数据，
      须跳过清理；
      Trend 不受影响——它存于 reports/allure-report/history，生成时由 report_generator
      重建进 allure-results/history。
      """
  ```
  **清理约定：**
  1. 入口：方向 conftest 的 `pytest_sessionstart(session)` 调用 `reset_allure_dir(session, allure_dir)`——**推荐把 `session` 传入**，内部才能做 worker/collectonly 判定；`session=None`（旧调用方式）时直接清理并 `logger.debug` 提示未启用守卫，保持向后兼容。
  2. **并行安全**：传入 session 时按 `getattr(session.config, "workerinput", None)` 判空，只有控制进程执行删除，各 worker 跳过，避免并发删目录报错。
  3. **`--collect-only` 守卫**：`session.config.option.collectonly` 为真时跳过清理——collect 阶段不写 allure 结果，清空只会丢上一轮数据且换不来干净统计。
  4. **只清结果、不留空**：清空 `allure-results/` 内文件（或重建目录），不删除 `reports/` 下的 Trend 历史。
  5. `pathlib` 实现，容错（目录不存在则忽略），根路径相对当前工作目录。
  6. **与统计过滤互补**：即使清理被跳过（如 xdist worker），`build_summary` 也只读 `*-result.json`，`-container.json` 不会污染 total。

  **方向 conftest 用法（开箱即得干净统计）：**
  ```python
  from base_framework import reset_allure_dir

  def pytest_sessionstart(session):
      reset_allure_dir(session, "allure-results")   # 并行安全 + collect-only 守卫，控制进程清空一次
  ```

- **3.9 失败工件挂载契约（trace / video / log 附件，驱动器无关）**：
  底座提供**驱动器无关**的失败工件挂载助手，供 Web / App / 接口失败的 hook 统一把 trace / video / 请求报文等**挂成 Allure 附件**，并自动进入 `build_summary` → report.json / 邮件。**具体采集**（如 Playwright trace）由对应方向实现，base 只负责挂载，不引入任何驱动：
  ```python
  def attach_failure_artifact(name, artifact_path, attach_type=None) -> bool:
      """把失败工件（trace/video/报文/图片）挂到 Allure，供 build_summary 聚合为附件。
      驱动器无关：只发起 allure.attach.file，不关心工件来自浏览器还是请求。
      attach_type 缺省按 artifact_path 扩展名推断；文件不存在时返回 False 不阻断。
      """
  ```
  **约定：**
  1. `name` 语义化（如 `"trace"`、`"video"`、`"response_body"`）；`artifact_path` 相对当前工作目录。
  2. 文件缺失 / 读不到 → 返回 `False` 并 `logger.debug`，**不影响用例结果**。
  3. **责任分层**：trace 的「开始 / 停止 / 导出」由方向层（Web=Playwright `context.tracing`）负责并返回工件路径；base 只做挂载与聚合。这样 base 不依赖具体驱动，API / App 方向用同一契约挂自己的工件。
  4. 方向失败 hook（`pytest_runtest_makereport`，`failed/broken` 且 `when=="call"`）里调用。
  5. **扩展名映射兼容**：`attach_type` 缺省按扩展名推断，映射表须注意 `allure.attachment_type` 在不同版本可用属性不同。**`WEBP` 在 allure-pytest<=2.13 不存在**（`AttributeError`），须降级为 `PNG`；建议用 `getattr(allure.attachment_type, "WEBP", allure.attachment_type.PNG)` 安全访问，或直接把 `.webp` 映射到 `PNG`。

  **方向 conftest 用法（失败时挂 trace）：**
  ```python
  from base_framework import attach_failure_artifact

  # 失败 hook 内：trace_path 由方向层 context.tracing 导出（Web 实现）
  if trace_path:
      attach_failure_artifact("trace", trace_path)
  ```

- **3.10 CI/CD 集成（按需生成）**：
  当用户要求“CI”“CI/CD”“GitHub Actions”“GitLab CI”或“Jenkins”时，为生成的底座工程提供真实可运行的流水线。平台选择规则：沿用目标仓库已有 CI 平台；若没有，则默认 GitHub Actions。除非用户明确要求多平台，不要同时生成多套配置。

  **CI 工作流必须覆盖：**
  1. 在 push、pull request 和手动触发时运行，并只授予完成 checkout、测试与归档所需的最小权限。
  2. 根据 `pyproject.toml` 的 `requires-python` 选择 Python 测试矩阵，不运行声明支持范围以外的版本；让 pip 根据各 Python 版本的 `Requires-Python` 解析兼容依赖。
  3. 缓存 pip 下载，缓存键至少包含操作系统、Python 版本和依赖清单；安装当前工程和测试依赖，不假定 `base_framework` 已发布到 PyPI 或已预装。
  4. 执行 `.py` 文件的 `py_compile`、`python -m pytest`、安装后导入公共 API 检查和 wheel 构建。任一步骤失败就让 CI 失败；禁止吞掉退出码、使用 `continue-on-error` 隐藏失败，或只打印错误后成功退出。
  5. 生成 `tests/test_config_reader.py`、`tests/test_report.py` 等离线单元测试，覆盖配置 / 环境变量覆盖、Allure 结果汇总和 `report.json` 输出。用 `tmp_path`、monkeypatch 和模拟数据；测试不得连接真实服务、发送 SMTP 邮件或依赖 Allure CLI。项目没有 pytest 测试依赖时，将 pytest 加入项目测试 / 可选依赖配置。
  6. 测试或构建失败后仍尽力归档 `allure-results/`、机器可读报告和已生成的 wheel；GitHub Actions 使用 `if: always()` 和适当的 `if-no-files-found`，不得因可选报告不存在而掩盖原始错误。
  7. 设置合理的作业超时。不在日志打印 Secrets、令牌、SMTP 授权码或业务凭据；通用底座流水线不要求真实业务 Secrets。
  8. 显式关闭 CI 中的自动开浏览器和邮件发送（如 `AUTO_OPEN_REPORT=false`、`SEND_REPORT_EMAIL=false`），避免依赖本机默认配置或误发通知。

  GitHub Actions 文件为 `${PROJ_DIR}/.github/workflows/ci.yml`。README 要说明 CI 触发条件、Python 矩阵、本地等效命令及失败时归档的工件。不要为了报告展示在 CI 中默认安装 / 启动 Allure CLI；无 Allure HTML 时归档原始结果和 JSON 汇总即可。

  CI 文件或 workflow 已存在时，先读取并扩展现有配置，保留已有 job、触发条件和用户自定义步骤；不得覆盖整个文件或创建重复 workflow。

  **CD/发布默认关闭，只有用户明确要求才生成：**
  - Python 包发布优先使用 GitHub Actions + PyPI Trusted Publishing（OIDC），不生成或索要明文 PyPI token。平台不支持 OIDC 时只引用用户需要放入平台 Secret Store 的变量名。
  - 发布只能由用户确认的 tag/release/受保护环境触发，并依赖同一提交 CI 和构建成功；构建一次后将同一 wheel/sdist 传给发布 job，避免重新构建出未验证的包。
  - 若包名、发布权限或触发条件尚未确认，只生成 CI 和发布配置说明，不添加会真正发布的 job；不默认部署到生产环境。
  - 不把发邮件或打开浏览器设为 CI 默认动作。邮件只在用户显式启用后通过 Secret Store 注入 SMTP 配置。

  GitLab CI/Jenkins：仅在用户指定或仓库已有该平台时生成 `.gitlab-ci.yml` / `Jenkinsfile`，遵守同样的 Python 版本、离线测试、构建、失败归档和凭据保护规则。流水线仅验证通用底座包，不宣称已端到端验证消费方 Web/App/API 的真实服务。

### Step 4：自检
- 对所有 `.py` 执行 `python -m py_compile`。

### Step 5：打包为外部二次框架
- `cd ${PROJ_DIR} && pip install -e .`，验证 `python -c "import base_framework; print(base_framework.__all__)"` 可导入且列出公共 API。

### Step 6：CI/CD（按需）
- 若用户要求，按 3.10 识别或选择平台，生成可执行的 CI 工作流与离线单元测试；只有用户明确要求发布时才加入受控 CD。

### Step 7：交付说明
- 二次框架包文件清单 + 安装命令 + `import` 用法示例 + 供各方向二次框架消费的方式；若生成 CI/CD，说明触发条件、Python 矩阵、归档工件、所需 Secrets，并区分实际执行验证与尚未运行的流水线。

## ⚠️ 约束与规范

1. **代码规范**：PEP 8、类型注解、`# -*- coding: utf-8 -*-`、中文注释、`pathlib.Path`、UTF-8；每个类与公共方法必须有 docstring；敏感信息不内置，由环境变量注入。
2. **幂等生成**：目标目录已存在则不重建、不覆盖已存在文件，只补齐缺失项。
3. **完整可运行**：所有生成文件必须完整可运行，禁止只写骨架或 `...` 占位符。
4. **严禁注入真实业务逻辑与具体驱动代码**：不引入 Playwright / WebDriver / Appium 等；本底座只做「logger + 报告 + 配置 + 邮件」能力包；方向扩展由各二次框架通过 `import base_framework` 完成。
5. **Allure CLI 是外部前置依赖**：`generate_report` 依赖系统 allure 命令（需 JDK 8+）。README 必须写明安装方式（npm/zip）、`ALLURE_BIN` 环境变量约定与 CLI 缺失时的行为（返回非 0 + 安装指引），报告生成失败不得静默。
6. **CI/CD 规则**：按用户要求生成；默认 CI、不默认发布 / 部署 / 发邮件，尽量沿用仓库已经选定的平台；不在源码或工作流中写入真实 Secrets；若用户要求 `loguru`、异步 API 等，按用户要求灵活调整。
7. **对外消费契约（供 Web / App / 接口二次框架使用）**：
   安装：`pip install -e ${PROJ_DIR}`（开发模式，改动即时生效）。
   ```python
   from base_framework import get_logger, ConfigReader, build_summary, write_json_report, EmailSender
   from base_framework.report_generator import generate_report

   logger = get_logger("my_direction")        # 直接获得日志
   config = ConfigReader("config/config.yaml")  # 直接读自己的配置
   summary = build_summary("allure-results")    # 直接出汇总
   write_json_report(summary, "reports/report.json")
   EmailSender().send_report(summary)           # 直接发邮件
   generate_report(open_report=True)            # 直接生成并打开 Allure 报告
   ```
   **并行执行（方向 conftest 的 `pytest_sessionfinish` 直接调用，开箱即得并行）：**
   ```python
   from base_framework import finalize_report_session, ConfigReader

   config = ConfigReader("config/config.yaml")

   def pytest_sessionfinish(session, exitstatus):
       finalize_report_session(
           session,
           auto_open=bool(config.get("report.auto_open", False)),
           email_enabled=bool(config.get("email.enabled", False)),
       )   # 内部自动做 worker 判空，只在控制进程收尾
   ```
   > **重要**：`auto_open` / `email_enabled` 缺省 `None` 时回退到环境变量 `AUTO_OPEN_REPORT` / `SEND_REPORT_EMAIL`（默认 `false`）。**方向层 conftest 必须从自身 config.yaml 显式传入**这两个值，否则测试执行后不会自动生成报告和发邮件。
   >
   > Web/App/接口方向二次框架，只需在 requirements 声明依赖 `base_framework`（`pip install -e`），并据此获得 logger / 配置 / 报告 / 邮件 / 报告生成，**不复制底座代码、不重复实现**。

8. **conftest fixture 作用域契约（ScopeMismatch 防范，真实判例）**：
   消费方 conftest 中，**fixture 作用域必须不小于其所有消费者的作用域**：session 级消费者（session 级 fixture、插件内部逻辑等）请求的 fixture 必须声明为 session 级，否则收集 / 运行即抛错。
   错误特征：`ScopeMismatch: You tried to access the 'base_url' fixture with a 'function' scoped request object`。
   真实判例：pytest-base-url 插件的 session 级 `_verify_url` 请求了默认 function 级的 `base_url` fixture，导致全量用例启动即报 ScopeMismatch。**正确修法**是把被请求的 fixture 作用域提升到不小于消费者的级别（`@pytest.fixture(scope="session")`）；**错误做法**是在用例层绕过 fixture 直读配置 / 环境变量——只是把设计问题藏进用例，报告与追溯链路都会变差。生成 / 修改消费方 conftest 时应主动核对：凡被 session 级 fixture 或插件请求的 fixture，作用域一律提到 session。

   **可编辑安装约定**：`pip install -e .` 后修改底座代码即时生效、无需重装；多个方向工程各自 `pip install -e` 同一底座时，底座改动对全部消费方立即生效——升级底座前应先跑一遍各方向冒烟再合入。

## ✅ 验证与自查

1. **功能校验**：所有 `.py` 过 `py_compile`；`pip install -e .` 后 `import base_framework` 可导入并 `print(__all__)` 正常。
2. **完整性校验（逐项核对输出物检查清单）**：
   - [ ] 生成可 `pip install -e .` 的二次框架包：`pyproject.toml` + `base_framework/`，包名 `base_framework`
   - [ ] `base_framework/__init__.py` 导出公共 API：get_logger / ConfigReader / get_config / build_summary / write_json_report / finalize_report_session / reset_allure_dir / attach_failure_artifact / EmailSender / generate_report
   - [ ] logger.py 控制台 + 文件，按天轮转、保留 30 天，`get_logger` 工厂；控制台对非 UTF-8 流（Windows GBK）做幂等 `reconfigure(errors="replace")` 兜底，中文日志不得触发 UnicodeEncodeError
   - [ ] config_reader.py 读 YAML、支持环境变量覆盖、`get_config` 便利函数（可喂自定义路径）
   - [ ] report.py 产出 `total/passed/failed/skipped/duration/failures[]/cases[]/env{}` 与 report.json；**只统计 `*-result.json`**（`-container.json` 等非用例文件不计入 total）；`cases[]` 含全量用例供邮件明细表；`env{}` 由方向层注入
   - [ ] **并行执行**：report.py 提供 `finalize_report_session`（含 `workerinput` 判空 + collectonly 守卫），仅在控制进程收尾，避免 xdist 下重复写报告 / 发邮件
   - [ ] **运行前清理**：report.py 提供 `reset_allure_dir(session=None, ...)`（worker 判空 + collectonly 守卫 + pathlib 容错，session=None 向后兼容），供方向 conftest 在 `pytest_sessionstart` 调用，避免跨运行 allure-results 污染统计与 collect-only 误清上一轮结果
   - [ ] **失败工件挂载**：report.py（或独立工具）提供 `attach_failure_artifact`（驱动器无关的 allure 附件助手，缺省按扩展名推断 attach_type、缺失容错），供方向失败 hook 挂 trace/video/报文；**扩展名映射须兼容 allure-pytest 版本差异**（`WEBP` 在 <=2.13 不存在，降级为 `PNG`）
   - [ ] email_sender.py SMTP 发送、失败不阻断；**截图内联须拼接 `allure_dir` 前缀找文件**（source 是 allure 目录内文件名，直接 `Path(source).exists()` 会 `False`）；模板三段式（环境信息→统计条→用例明细），**用例明细表设 `table-layout:fixed`**，列宽比例（名称25%/状态6%/耗时8%/错误40%/截图21%），**斑马纹**奇偶行交替背景色，截图 `width=120px` 内联，统计条不挤一行不重复耗时，附件只附 trace（与用例名关联），失败用例展示完整断言错误信息
   - [ ] report_generator.py 提供 `generate_report(open_report)`，**allure CLI 四级定位回退链**（which → `ALLURE_BIN` → npm 全局 → 局部 node_modules）、CLI 缺失返回非 0 并附安装指引（JDK 8+ / npm install -g allure-commandline）、打开报告优先 `allure open` **禁止 `file://` 直开**（SPA 数据加载会空白）、保留 Trend、规避中文路径
   - [ ] `pyproject.toml` 与 `requirements.txt` 依赖清单一致；README 写明 allure CLI 前置依赖与安装指引；交付说明含 fixture 作用域契约提示（session 级消费者请求的 fixture 须为 session 级，ScopeMismatch 属设计问题须提升作用域修复）
   - [ ] 所有 .py 过 py_compile
   - [ ] `pip install -e .` 后 `import base_framework` 可导入并 `print(__all__)` 正常
   - [ ] 未发现任何真实业务逻辑与具体驱动代码
   - [ ] 若用户要求 CI/CD：平台沿用仓库现有选择，或无既有平台时默认 GitHub Actions；Python 矩阵遵守 `requires-python`；安装、导入、pytest 和 wheel 构建任一失败都会让 CI 失败
   - [ ] 若用户要求 CI/CD：单元测试无需外部服务、SMTP 凭据或 Allure CLI；失败时尽力归档已生成的结果、JSON 报告和 wheel；未硬编码凭据或默认启用邮件
   - [ ] 若涉及 CD：只有用户明确要求发布时才生成发布 job；发布受控触发，并使用同一 CI 验证过的构建制品
3. **最终确认**：输出完整的验证报告，明确标注任务是否 100% 完成。

## 📚 引用资源

- **对外 import API 示例**：`from base_framework import get_logger, ConfigReader, build_summary, write_json_report, EmailSender; from base_framework.report_generator import generate_report`，供 Web/App/接口二次框架 `pip install -e` 后直接复用 logger / 配置 / 报告 / 邮件 / 报告生成。
- **打包与安装**：`pyproject.toml`（包名 `base_framework`，`pip install -e .` 开发模式，改动即时生效）。
- **CI/CD 模板**：`${PROJ_DIR}/.github/workflows/ci.yml`（GitHub Actions 默认）、`.gitlab-ci.yml` / `Jenkinsfile`（仓库既有平台时复用）；离线单元测试 `tests/test_config_reader.py`、`tests/test_report.py`；`.gitignore` 忽略测试 / 构建 / 报告产物与本地凭据。
- **README 必含**：安装与对外 import API 用法、Allure CLI 前置依赖（JDK 8+ / npm install -g allure-commandline / `ALLURE_BIN`）与 CLI 缺失行为、CI 触发条件与归档工件、fixture 作用域契约提示。

完成后向用户交付**外部可用的二次框架包**目录 + 安装命令（`pip install -e .`）+ 对外 `import` API 示例，并说明 Web/App/接口二次框架如何 `pip install -e` 后直接复用 logger / 报告 / 邮件 / 报告生成。
若本次要求 CI/CD，还要列出工作流路径、触发条件、测试 / 构建结果、失败时归档工件及尚待用户配置的 Secrets；没有实际运行的 CI/CD 不得描述为已通过。
