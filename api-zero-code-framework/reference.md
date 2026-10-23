# API 框架模块契约（零代码 · 单 API 文件 + 业务组合复用 · 多类型断言）

本框架**零代码**：以 **单个 API 一个 YAML 文件** 为可复用单元，业务文件通过 `steps` **引用多个单 API 文件（或嵌套另一份 flow 业务）**组合成链路（定义一次、多处复用）。每个 API 自带 `request` + 提取（`extract`/`extract_global`）+ 多类型软断言（`validate`）。`engine/` 通用代码执行，不随业务变化。生成代码时遵守本契约（与 SKILL.md 一致，本文是详细真相源）。**用例仅 YAML（`.yaml`/`.yml`）；YAML 内的 `json:` 指 HTTP 请求体类型，与用例文件格式无关。**

> 两种文件：**① 单 API 定义文件**（`testcases/apis/`，一个文件 = 一个 API，可复用组件，**不直接收集**）；**② 业务编排文件**（`testcases/flows/`，`steps` 引用多个单 API 文件（或嵌套另一份 flow 业务），**展开为多个 API Item（`业务title :: API name`），整体即一个 business flow**）。业务内步骤顺序执行、共享上下文；跨业务用 `extract_global` + `${read_yaml(name)}`。断言支持 equals/比较/包含/集合/长度/类型/正则/存在性/schema/状态码 多类型；API 内软断言，**任一步骤失败则本 case 失败、后续步骤不再执行（下游 Item 以 skip 标记）**。

## 依赖方向
```
engine/  →  common/  →  utils/  →  (纯函数)
           （common/ 同时含日志、配置、报告等配套模块）
testcases/apis/*   可复用单 API 组件（被 flows 引用，不直接收集）
testcases/flows/*  业务编排（引用 apis 或嵌套 flows，被收集为多个 API Item）
```
`utils` 不 import 上层；`common` 不 import `engine` 与 yaml 业务；`engine` 不 import 具体接口名（只按 `steps` 引用的 API 逐项执行）。

---

## 零、配套模块（分层：`common/` 核心层 + `utils/` 纯函数 + `engine/reporting/` 报告与通知）

框架运行所需的日志、配置、报告等配套模块随框架一起生成，分层放置。`common/` 为核心层；`utils/` 为纯函数；报告与通知编排（由 `conftest` 会话钩子驱动）放在 `engine/reporting/`。生成框架时各模块源码见本节下方「模块源码」：

- `common/config_reader.py` —— `ConfigReader` / `get_config`（进程内缓存）
- `common/request_client.py` —— `ApiClient` / `ApiResponse` / `ApiExecError`（源码见 §五）
- `common/context.py` —— `ApiContext`（extract 仅本业务 / extract_global 跨业务共享）
- `common/data_loader.py` —— `load_case` / `load_constants`（share ⊕ env 深合并）
- `common/paths.py` —— 集中项目路径（data/config/artifacts/allure-results），解耦 CWD
- `utils/redact.py` —— 统一脱敏（请求/响应/证据/邮件覆盖敏感字段）
- `engine/reporting/report.py` —— `build_summary` / `write_json_report` / `finalize_report_session` / `reset_allure_dir` / `attach_failure_artifact` / `attach_failure_text`
- `engine/reporting/mailer.py` —— `send_report_email` / `_build_html`
- `engine/reporting/report_generator.py` —— `generate_report`

`conftest` / `collector` / `request_client` 统一以 `from common.xxx import ...` 复用（如 `import logging`、`from engine.reporting.report import finalize_report_session`）；报告三件套在 `engine/reporting/`，内部用相对导入（`from .report_generator import ...` / `from .mailer import ...`）。

**框架内公共 API**：`common/`：`ConfigReader / get_config / ApiClient / assert_spec / build_step_spec / run_flow`；`engine/reporting/`：`build_summary / write_json_report / finalize_report_session / reset_allure_dir / attach_failure_artifact / attach_failure_text / generate_report / send_report_email`。

## 强约束清单（速查）

生成与排障时逐项对照；详细契约见各分节。

| # | 约束 | 说明 / 详见 |
| --- | --- | --- |
| 1 | 零代码边界 | 业务完全由 YAML 表达（单 API 文件 + flows 引用），不含 Python 测试代码 |
| 2 | 单文件复用模型 | 单个 API 一个文件（`apis/`）+ 业务 `steps` 引用（`flows/`/嵌套另一 `flows/`）；跨接口关联用 `extract_global` + `${read_yaml(name)}`；差异用 `with` |
| 3 | 仅 YAML | 用例只支持 `.yaml`/`.yml`；`json:` 指 HTTP 请求体类型，与文件格式无关 |
| 4 | 软断言 + 硬停止 | 规则与错误格式以第三节/第八节为准；业务内任一失败即停下游 |
| 5 | 配套模块来源 | 日志/配置/报告/邮件由 `common/` 与 `engine/reporting/` 提供，只依赖 `requirements.txt` 已声明三方包，不引入额外依赖 |
| 6 | 鉴权单点 | Token/请求头注入只在 `common/request_client.py` |
| 7 | 断言可追溯 | `validate` 以声明式写在 YAML 中 |
| 8 | 中文 UTF-8 | 文件与日志均 UTF-8 |
| 9 | 配置分层 | `config/config.yaml` 配 base_url/报告/数据/env/mail；`pytest.ini` 统一开关；失败重试交 `pytest-rerunfailures`；**环境变量覆盖仅在「非空」时生效，空串/未设置回落配置文件（避免 CI 未设置的 secret 解析为空串吞掉 base_url 等配置）** |
| 10 | base_url 缺失即报错 | `config.yaml` 未配 base_url 则运行抛配置错误，不收集、不 skip，禁止无服务空跑；**`BASE_URL` 为空环境变量不视为已配置、亦不覆盖配置** |
| 11 | 默认头单一来源 | 合并优先级 `default_headers < feature.headers < request/with.headers`；`Authorization` 仅无时注入 |
| 12 | 数据/结构分离 | 敏感值（账号密码/token）只进 `data/<env>.yaml`，不进 `share.yaml`；其余常量进 `data/` |
| 13 | 常见坑 | `equals` 字符串↔数字数值宽容；支持 `json/form/data/files` 四体；Bearer/裸 token 以实证为准；并行 `--dist loadscope` 且 `extract_global` 不跨 worker |
| 14 | 报告开关独立 | `enable_allure_report`/`auto_open_report`/`enable_email_report` 环境变量可覆盖；重试不自行实现，`historyId` 聚合去重 |
| 15 | 多环境零改动 | 优先级 `--env` > `TEST_ENV` > `config.yaml.env` > `dev` |
| 16 | 邮件不阻断 | 缺配置/异常仅 `logging.warning` 返回 `False`；`smtp_password` 用 `MAIL_SMTP_PASSWORD` 注入，勿明文 |
| 17 | 统一脱敏 | 请求/响应/证据/邮件敏感字段由 `utils.redact` 覆盖（含 `X-Auth-Token` 等变体） |
| 18 | 报告读嵌套配置 | `report` 用 `get_config().get_section("report")` 读 `allure_dir/report_dir/json_path` |
| 19 | 会话级隔离 | `conftest.pytest_sessionstart` 调 `ApiContext.reset_global()` 防跨 case 全局变量污染 |
| 20 | 断言类型分派完整 | `_check` 须覆盖全部类型**及别名**（`eq/ne/gt/lt/gte/lte/matches`、`status_code`/`status`）；`status_code`/`status` = actual 隐含 `resp.status_code` 的 equals，漏分派会误报「未知断言类型」（详见 §六） |
| 21 | pytest.ini bool 开关禁行内注释 | `type="bool"` 的 ini 值行内 `# ...` 会被当作值 → `ValueError: invalid truth value`；注释只能单独成行写在开关上方（详见 §十一-7） |

### common/ 模块源码（单一真相源，原样写入）

**`common/config_reader.py`**：
```python
# -*- coding: utf-8 -*-
"""YAML 配置读取 + 环境变量覆盖（顶层 ENV_KEY 或 {节名}_{子键}）。"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


class ConfigReader:
    """加载 YAML 配置并提供 get / get_section / to_dict，支持环境变量覆盖。"""

    def __init__(self, config_path: Optional[str] = None) -> None:
        self._path = Path(config_path) if config_path else None
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if self._path and self._path.exists() and yaml is not None:
            return yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        return {}

    def get(self, key: str, default: Any = None) -> Any:
        """顶层字段；环境变量 KEY(大写) 仅在「非空」时优先于配置文件；空字符串/未设置均回落配置文件。"""
        env = os.environ.get(key.upper())
        if env is not None and env.strip() != "":
            return _coerce(env)
        return self._data.get(key, default)

    def get_section(self, section: str) -> Dict[str, Any]:
        """整段读取；节内子键支持 {SECTION}_{SUBKEY}(大写) 环境变量覆盖（空值不覆盖配置文件）。"""
        base = dict(self._data.get(section, {}) or {})
        prefix = f"{section.upper()}_"
        for k, v in os.environ.items():
            if k.startswith(prefix) and v.strip() != "":
                base[k[len(prefix):].lower()] = _coerce(v)
        return base


def _coerce(value: str) -> Any:
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [x.strip() for x in inner.split(",") if x.strip()] or []
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null", ""):
        return None
    try:
        return int(v)
    except ValueError:
        return v


_CONFIG_CACHE: Dict[str, "ConfigReader"] = {}


def get_config(config_path: Optional[str] = None) -> ConfigReader:
    """便利工厂：优先 config_path，其次 API_FRAMEWORK_CONFIG，再回落 config/config.yaml。
    同一路径进程内缓存，避免重复 yaml.safe_load。"""
    path = config_path or os.environ.get("API_FRAMEWORK_CONFIG", "config/config.yaml")
    key = str(Path(path).resolve())
    cached = _CONFIG_CACHE.get(key)
    if cached is not None:
        return cached
    inst = ConfigReader(path)
    _CONFIG_CACHE[key] = inst
    return inst
```

**`common/request_client.py`**（源码见 §五「请求会话」）

**`common/context.py`**：
```python
# -*- coding: utf-8 -*-
"""测试上下文：本业务可见变量（extract）+ 跨业务全局变量（extract_global，进程级）。"""


class ApiContext:
    """一次业务运行的上下文；extract 仅本业务可见，extract_global 写入模块级 _GLOBAL（同进程跨 case 共享）。"""

    _GLOBAL: dict = {}

    def __init__(self, biz_title: str = "", base_dir=None, apis_dir=None) -> None:
        self.biz_title = biz_title
        self.base_dir = base_dir
        self.apis_dir = apis_dir
        self.data: dict = {}

    def set(self, key: str, value) -> None:
        self.data[key] = value

    def set_global(self, key: str, value) -> None:
        type(self)._GLOBAL[key] = value

    def get(self, key: str, default=None):
        if key in self.data:
            return self.data[key]
        return type(self)._GLOBAL.get(key, default)

    def runtime(self) -> dict:
        """运行时变量：全局在前、实例在后（实例覆盖全局）。供模板解析使用。"""
        merged = dict(type(self)._GLOBAL)
        merged.update(self.data)
        return merged

    @classmethod
    def reset_global(cls) -> None:
        cls._GLOBAL = {}
```

**`common/data_loader.py`**：
```python
# -*- coding: utf-8 -*-
"""YAML 用例加载 + 测试数据常量加载（share ⊕ env 深合并）。"""
import os
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

from utils.dicts import deep_merge
from common.paths import DATA_DIR


def _load_yaml_file(path) -> Dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"用例文件不存在: {p}")
    if yaml is None:  # pragma: no cover
        raise RuntimeError("pyyaml 未安装，请执行 pip install -r requirements.txt")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def load_case(path) -> Dict[str, Any]:
    """加载单 API / 业务 YAML 文件。"""
    return _load_yaml_file(path)


def load_constants(env: str = "dev") -> Dict[str, Any]:
    """加载 data/share.yaml 并按 env 深合并 data/<env>.yaml，得到当前环境常量命名空间。"""
    base = _load_yaml_file(DATA_DIR / "share.yaml")
    env_file = DATA_DIR / f"{env}.yaml"
    if env_file.is_file():
        over = _load_yaml_file(env_file)
        base = deep_merge(base, over)
    return base
```

**`common/paths.py`**：
```python
# -*- coding: utf-8 -*-
"""项目路径集中管理：相对路径基于项目根，可由环境变量 PROJECT_ROOT 覆盖。

框架代码位于 <root>/common/paths.py，向上两级即项目根；以库方式导入时可用
PROJECT_ROOT 指向运行根（如 pytest 的 rootdir），避免所有相对路径硬绑定 CWD。
"""
import os
from pathlib import Path

_ROOT_ENV = os.environ.get("PROJECT_ROOT")


def _root() -> Path:
    if _ROOT_ENV:
        return Path(_ROOT_ENV)
    return Path(__file__).resolve().parent.parent


ROOT = _root()
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
ARTIFACTS_DIR = ROOT / "artifacts"
ALLURE_RESULTS_DIR = ROOT / "allure-results"
REPORTS_DIR = ROOT / "reports"
ALLURE_REPORT_DIR = REPORTS_DIR / "allure-report"
REPORT_JSON = REPORTS_DIR / "report.json"
```

**`utils/redact.py`**：
```python
# -*- coding: utf-8 -*-
"""日志/证据/邮件中的敏感字段脱敏（统一实现，供 executor 与 request_client 复用）。"""
from typing import Any

# 忽略大小写与 _/- 后的敏感 key；命中则其值替换为 ***（安全侧偏严：含敏感子串即命中）
_SENSITIVE = {
    "authorization", "cookie", "token", "password", "passwd",
    "secret", "accesstoken", "refreshtoken",
}


def redact(obj: Any) -> Any:
    """递归脱敏：敏感 key 的值替换为 ***（dict/list 递归；标量原样返回）。"""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key = str(k).lower().replace("_", "").replace("-", "")
            out[k] = "***" if any(s in key for s in _SENSITIVE) else redact(v)
        return out
    if isinstance(obj, (list, tuple)):
        return type(obj)(redact(v) for v in obj)
    return obj
```

**`engine/reporting/report.py`**：
```python
# -*- coding: utf-8 -*-
"""汇总 Allure 结果 -> report.json；并行安全收尾与清理；失败工件挂载。"""
import json
import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.config_reader import get_config
from common.paths import ALLURE_RESULTS_DIR, REPORTS_DIR, ALLURE_REPORT_DIR, REPORT_JSON


def _attach_type_for(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext == "webp":  # allure-pytest<=2.13 无 WEBP，降级为 PNG
        try:
            import allure  # noqa: F401
            from allure_commons.types import AttachmentType
            getattr(AttachmentType, "WEBP")
            return "webp"
        except Exception:
            return "png"
    table = {
        "png": "png", "jpg": "jpg", "jpeg": "jpg", "gif": "gif", "bmp": "bmp",
        "txt": "txt", "log": "txt", "html": "html", "json": "json",
        "xml": "xml", "zip": "zip",
    }
    return table.get(ext, "txt")


def attach_failure_artifact(name: str, artifact_path: str,
                            attach_type: Optional[str] = None) -> bool:
    """驱动器无关地把失败工件挂到 Allure（仅包装 allure.attach.file）。文件缺失返回 False 不阻断。"""
    p = Path(artifact_path)
    if not p.is_file():
        return False
    try:
        import allure
        allure.attach.file(str(p), name=name, attachment_type=_attach_type_for(p.suffix))
        return True
    except Exception:
        return False


def attach_failure_text(name: str, text: str) -> bool:
    """把可读的失败详情直接内联挂到 Allure（TEXT 类型，便于在报告里直接查看）。"""
    try:
        import allure
        from allure_commons.types import AttachmentType
        allure.attach(str(text), name=name, attachment_type=AttachmentType.TEXT)
        return True
    except Exception:
        return False


def _first_image(allure_dir: Path, attachments: Any) -> Optional[str]:
    """取该 case 第一张图片附件（失败截图）在 allure-results 下的路径。"""
    for a in (attachments or []):
        if isinstance(a, dict) and str(a.get("type", "")).startswith("image"):
            src = a.get("source")
            if src:
                p = allure_dir / src
                return str(p) if p.is_file() else None
    return None


def _collect_attachments(node: Any) -> List[Dict[str, Any]]:
    """递归收集 case（含嵌套 step）下的所有附件条目。"""
    out: List[Dict[str, Any]] = []
    if isinstance(node, dict):
        for a in (node.get("attachments") or []):
            if isinstance(a, dict):
                out.append(a)
        for st in (node.get("steps") or []):
            if isinstance(st, dict):
                out.extend(_collect_attachments(st))
    return out


def _first_text(allure_dir: Path, case_data: Any) -> Optional[str]:
    """取该 case 的「失败详情」文本附件（接口/请求/响应/错误全貌，干净无日志）。

    allure.attach 在 step 内调用时附件挂在 step.attachments 下，故递归 steps 收集；
    仅按名称命中「失败详情」（只有失败用例才会挂载）。绝不回退到 pytest 的 log 附件，
    否则会混入 engine.collector 的 INFO/ERROR 日志及被截断的现场，污染邮件错误列。
    """
    atts = _collect_attachments(case_data) if isinstance(case_data, dict) else []
    for a in atts:
        if isinstance(a, dict) and "失败详情" in str(a.get("name", "")):
            src = a.get("source")
            if src:
                p = allure_dir / src
                if p.is_file():
                    return p.read_text(encoding="utf-8", errors="ignore")
    return None


def build_summary(allure_dir: str = str(ALLURE_RESULTS_DIR)) -> Dict[str, Any]:
    """解析 allure-results，按 historyId 聚合（一个 flow = 一个 case）。

    pytest-rerunfailures 每次重跑会写一个独立的 *-result.json，但共享同一
    historyId；此处按 historyId 分组并取最终一次（stop 最大）的状态作为该
    case 的最终结果，保证「重试同一 case 仍为一条」，不会因重试次数增加而让
    用例计数变多（Allure HTML 也按 historyId 合并为一条，仅带重试记录）。
    """
    ad = Path(allure_dir)
    latest: Dict[str, Any] = {}   # historyId -> (stop, data)
    order: List[str] = []
    passed = failed = skipped = broken = 0
    duration = 0.0
    if ad.is_dir():
        for f in ad.glob("*-result.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            hid = data.get("historyId") or data.get("testCaseId") or data.get("name") or f.stem
            stop = data.get("stop", 0) or 0
            if hid not in latest or stop >= latest[hid][0]:
                latest[hid] = (stop, data)
                if hid not in order:
                    order.append(hid)
    cases: List[Dict[str, Any]] = []
    for hid in order:
        data = latest[hid][1]
        status = data.get("status", "unknown")
        name = data.get("name", hid)
        start = data.get("start", 0) or 0
        stop = data.get("stop", 0) or 0
        dur = round(max(0.0, (stop - start) / 1000.0), 3)
        duration += dur
        status_details = data.get("statusDetails") or {}
        err_msg = data.get("statusMessage")
        if not err_msg and isinstance(status_details, dict):
            err_msg = status_details.get("message")
        cases.append({
            "name": name, "status": status, "duration": dur,
            "error": err_msg,
            "error_detail": _first_text(ad, data),
            "screenshot": _first_image(ad, data.get("attachments")),
        })
        if status == "passed":
            passed += 1
        elif status == "failed":
            failed += 1
        elif status == "broken":
            broken += 1
        elif status == "skipped":
            skipped += 1
    return {
        "total": len(cases), "passed": passed, "failed": failed,
        "broken": broken, "skipped": skipped, "duration": round(duration, 3),
        "cases": cases, "env": {},
    }


def write_json_report(summary: Dict[str, Any], out_path: str = str(REPORT_JSON)) -> Path:
    """写机器可读 report.json。"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _is_worker(session: Any) -> bool:
    cfg = getattr(session, "config", None)
    return bool(cfg and getattr(cfg, "workerinput", None))


def reset_allure_dir(session: Any = None, allure_dir: str = str(ALLURE_RESULTS_DIR)) -> None:
    """并行安全清理：仅控制进程、非 collect-only 时清空结果目录。"""
    if session is not None:
        if _is_worker(session):
            return
        option = getattr(session.config, "option", None)
        if option and getattr(option, "collectonly", False):
            return
    ad = Path(allure_dir)
    if ad.is_dir():
        shutil.rmtree(ad, ignore_errors=True)
    ad.mkdir(parents=True, exist_ok=True)


def finalize_report_session(session: Any, allure_dir: str = str(ALLURE_RESULTS_DIR),
                            report_out: str = str(REPORT_JSON),
                            auto_open: Optional[bool] = None,
                            report_enabled: Optional[bool] = None,
                            enable_email: Optional[bool] = None,
                            env: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """并行安全收尾：仅控制进程执行一次 汇总->report.json->(可选)Allure->(可选)邮件。
    auto_open/report_enabled/enable_email 通常由 conftest.pytest_sessionfinish 从 pytest.ini + 环境变量注入。"""
    if _is_worker(session):
        return None
    option = getattr(session.config, "option", None)
    if option and getattr(option, "collectonly", False):
        return None
    if auto_open is None:
        auto_open = os.environ.get("AUTO_OPEN_REPORT", "true").lower() == "true"
    if report_enabled is None:
        report_enabled = os.environ.get("ENABLE_ALLURE_REPORT", "true").lower() == "true"
    if enable_email is None:
        enable_email = os.environ.get("ENABLE_EMAIL_REPORT", "false").lower() == "true"
    cfg = get_config("config/config.yaml")
    allure_dir_resolved = str(cfg.get_section("report").get("allure_dir", allure_dir))
    report_dir = str(cfg.get_section("report").get("report_dir", "reports/allure-report"))
    summary = build_summary(allure_dir_resolved)
    merged_env = {
        "env": str(cfg.get("env", "dev")),
        "base_url": str(cfg.get("base_url", "")),
        "app": str(cfg.get("app", "")),
        "device": str(cfg.get("device", "")),
        "os": f"{platform.system()} {platform.release()}",
        "report_dir": report_dir,
        "report_url": f"{report_dir} (本地，已自动打开)" if auto_open else report_dir,
    }
    if env:
        merged_env.update(env)
    summary["env"] = merged_env
    write_json_report(summary, str(cfg.get_section("report").get("json_path", report_out)))
    # 生成报告与自动打开是两个独立开关：enable_allure_report / auto_open_report
    if report_enabled:
        try:
            from .report_generator import generate_report
            generate_report(open_report=bool(auto_open))
        except Exception:
            pass
    if enable_email:
        try:
            from .mailer import send_report_email
            report_url = "http://127.0.0.1:4040/" if auto_open else report_dir
            send_report_email(summary=summary, report_url=report_url, report_dir=report_dir)
        except Exception as e:
            logging.getLogger("engine.reporting.report").warning("邮件发送失败：%s", e)
    return summary
```

**`engine/reporting/mailer.py`**：
```python
# -*- coding: utf-8 -*-
"""邮件通知：测试完成后把 Allure 报告摘要（或报告 zip）通过 SMTP 发出。

配置从 config/config.yaml 的 `mail:` 节读取，环境变量 MAIL_* 可覆盖任意子键：
  smtp_host / smtp_port / smtp_user / smtp_password / sender / receivers
  use_ssl / use_tls / subject_prefix / attach_report
开关由 pytest.ini 的 enable_email_report 控制（环境变量 ENABLE_EMAIL_REPORT 可覆盖）。
"""
import html
import io
import logging
import smtplib
import ssl
import zipfile
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.config_reader import get_config

log = logging.getLogger("engine.reporting.mailer")

_TD = "border:1px solid #d0d7de;padding:6px 10px;font-size:13px;"
_LBL = _TD + "background:#f6f8fa;color:#57606a;"
_STATUS_COLOR = {"passed": "#1a7f37", "failed": "#cf222e",
                 "broken": "#bf8700", "skipped": "#6e7781"}


def _td(text: Any, style: str = _TD) -> str:
    return f"<td style='{style}'>{html.escape(str(text))}</td>"


def _td_raw(html_content: str, style: str = _TD) -> str:
    return f"<td style='{style}'>{html_content}</td>"


def _status_cell(status: str) -> str:
    color = _STATUS_COLOR.get(status, "#57606a")
    return (f"<td style='{_TD}color:{color};font-weight:bold;'>"
            f"{html.escape(status.upper())}</td>")


def _load_mail_config() -> Dict[str, Any]:
    return get_config("config/config.yaml").get_section("mail") or {}


def _build_html(summary: Dict[str, Any], report_url: str) -> str:
    env_info = summary.get("env", {}) or {}
    env = str(env_info.get("env", ""))
    base_url = str(env_info.get("base_url", ""))
    total = int(summary.get("total", 0) or 0)
    passed = int(summary.get("passed", 0) or 0)
    failed = int(summary.get("failed", 0) or 0)
    broken = int(summary.get("broken", 0) or 0)
    skipped = int(summary.get("skipped", 0) or 0)
    duration = float(summary.get("duration", 0) or 0)
    rate = f"{passed / total * 100:.1f}%" if total else "-"
    cases: List[Dict[str, Any]] = summary.get("cases", []) or []

    # 信息区：测试时长 / 被测服务 / 环境 / Allure 报告链接
    dur_str = f"{duration:.2f}s"
    link = f"<a href='{html.escape(report_url, quote=True)}'>{html.escape(report_url)}</a>"
    info = (
        "<table style='border-collapse:collapse;'>"
        f"<tr>{_td('测试时长', _LBL)}{_td(dur_str)}"
        f"{_td('被测服务', _LBL)}{_td(base_url)}</tr>"
        f"<tr>{_td('环境', _LBL)}{_td(env)}"
        f"{_td('Allure报告', _LBL)}<td style='{_TD}'>{link}</td></tr>"
        "</table>"
    )

    # 统计区：总数 / 通过 / 失败 / 异常 / 跳过 / 通过率
    stat_items = (
        ("用例总数", str(total), ""),
        ("通过", str(passed), "color:#1a7f37;font-weight:bold;"),
        ("失败", str(failed), "color:#cf222e;font-weight:bold;"),
        ("异常", str(broken), "color:#bf8700;font-weight:bold;"),
        ("跳过", str(skipped), ""),
        ("通过率", rate, "font-weight:bold;"),
    )
    stats = "<table style='border-collapse:collapse;'><tr>" + "".join(
        f"{_td(name, _LBL)}<td style='{_TD}{style}'>{val}</td>"
        for name, val, style in stat_items
    ) + "</tr></table>"

    # 用例明细：全部用例（名称/状态/耗时/错误信息，无截图列）
    def _row(c: Dict[str, Any]) -> str:
        dur = f"{float(c.get('duration', 0) or 0):.2f}s"
        err = html.escape(str(c.get("error_detail") or c.get("error") or "")).replace("\n", "<br>")
        return (f"<tr>{_td(c.get('name', ''))}"
                f"{_status_cell(str(c.get('status', '')))}"
                f"{_td(dur)}{_td_raw(err)}</tr>")

    rows = "".join(_row(c) for c in cases)
    detail = (
        "<h3 style='margin:16px 0 8px;'>用例明细</h3>"
        "<table style='border-collapse:collapse;'>"
        f"<tr>{_td('用例名称', _LBL)}{_td('状态', _LBL)}"
        f"{_td('耗时', _LBL)}{_td('错误信息', _LBL)}</tr>"
        f"{rows}</table>"
    )

    return (
        "<html><body style=\"font-family:'Microsoft YaHei',Arial,sans-serif;color:#24292f;\">"
        f"<h2>API 自动化测试报告</h2>{info}"
        f"<div style='height:12px;'></div>{stats}{detail}"
        "</body></html>"
    )


def _zip_report(report_dir: str) -> Optional[bytes]:
    """把报告目录打成 zip（内存中），便于作为邮件附件。"""
    rd = Path(report_dir)
    if not rd.is_dir():
        return None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in rd.rglob("*"):
            if p.is_file():
                zf.write(p, str(p.relative_to(rd)))
    return buf.getvalue()


def send_report_email(summary: Optional[Dict[str, Any]] = None,
                      report_url: str = "",
                      report_dir: str = "reports/allure-report",
                      extra: Optional[Dict[str, Any]] = None) -> bool:
    """发送测试报告邮件；缺 SMTP 配置或失败均返回 False 且不抛异常（不阻断主流程）。"""
    cfg = _load_mail_config()
    smtp_host = str(cfg.get("smtp_host") or "").strip()
    receivers = cfg.get("receivers") or []
    if isinstance(receivers, str):
        receivers = [r.strip() for r in receivers.split(",") if r.strip()]
    sender = str(cfg.get("sender") or "").strip()
    if not smtp_host or not receivers:
        log.warning("邮件未发送：缺少 smtp_host 或 receivers 配置（config.yaml 的 mail: 节）")
        return False
    if not sender:
        sender = receivers[0]

    smtp_port = int(cfg.get("smtp_port") or 465)
    smtp_user = str(cfg.get("smtp_user") or "").strip()
    smtp_password = str(cfg.get("smtp_password") or "").strip()
    use_ssl = bool(cfg.get("use_ssl", True))
    use_tls = bool(cfg.get("use_tls", False))
    subject_prefix = str(cfg.get("subject_prefix") or "[API 自动化]").strip()
    attach_report = bool(cfg.get("attach_report", True))

    summary = summary or {}
    env_info = summary.get("env", {}) or {}
    env = env_info.get("env", "")
    failed = summary.get("failed", 0)
    broken = summary.get("broken", 0)
    passed = summary.get("passed", 0)
    total = summary.get("total", 0)
    subject = f"{subject_prefix} 环境 {env}：通过{passed}/共{total}，失败{failed} 异常{broken}"

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(receivers)
    msg["Subject"] = subject
    msg.attach(MIMEText(_build_html(summary, report_url), "html", "utf-8"))

    if attach_report:
        data = _zip_report(report_dir)
        if data:
            part = MIMEApplication(data, Name="allure-report.zip")
            part["Content-Disposition"] = 'attachment; filename="allure-report.zip"'
            msg.attach(part)

    mode = "SSL" if use_ssl else ("STARTTLS" if use_tls else "plain")
    log.info("正在连接 SMTP %s:%s（模式=%s）发送邮件...", smtp_host, smtp_port, mode)
    try:
        ctx = ssl.create_default_context()
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30, context=ctx) as s:
                if smtp_user:
                    s.login(smtp_user, smtp_password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as s:
                if use_tls:
                    s.starttls(context=ctx)
                if smtp_user:
                    s.login(smtp_user, smtp_password)
                s.send_message(msg)
        log.info("测试报告邮件已发送至 %s", ", ".join(receivers))
        return True
    except Exception as e:
        log.warning("邮件发送失败（%s:%s 模式=%s）：%s", smtp_host, smtp_port, mode, e)
        return False
```

**`engine/reporting/report_generator.py`**：
```python
# -*- coding: utf-8 -*-
"""Allure 报告生成：定位 allure CLI → 写入环境信息 → 生成 HTML → 可选 detached 打开。"""
import datetime
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional

from common.paths import ALLURE_RESULTS_DIR, ALLURE_REPORT_DIR


def _candidate_bins() -> list:
    cands = []
    if os.environ.get("ALLURE_BIN"):
        cands.append(os.environ["ALLURE_BIN"])
    # Windows 上 subprocess 无法直接解析 "allure" -> allure.bat，用 shutil.which
    # 借助 PATHEXT 拿到含扩展名的真实路径（如 ...\allure.bat），否则误判“未检测到”。
    resolved = shutil.which("allure")
    if resolved:
        cands.append(resolved)
    return cands


def _allure_bin() -> Optional[str]:
    """返回可用的 allure 路径；缺失（或 Java 不可运行）返回 None。"""
    for c in _candidate_bins():
        try:
            subprocess.run([c, "--version"], capture_output=True, text=True, timeout=30)
            return c
        except Exception:
            continue
    return None


def _allure_version(bin_path: str) -> str:
    try:
        out = subprocess.run([bin_path, "--version"], capture_output=True,
                             text=True, timeout=30)
        return (out.stdout or out.stderr).strip()
    except Exception:
        return ""


def write_allure_environment(allure_dir: str = str(ALLURE_RESULTS_DIR),
                             extra: Optional[dict] = None) -> None:
    """写 allure-results/environment.properties，Allure 报告 Overview 的 Environment 控件展示测试环境。"""
    from common.config_reader import get_config
    ad = Path(allure_dir)
    ad.mkdir(parents=True, exist_ok=True)
    cfg = get_config("config/config.yaml")
    av = _allure_version(_allure_bin() or "allure")
    # 键名不能含空格：environment.properties 按 Java Properties 解析，空格会被当作键值分隔符
    info = {
        "Environment": str(cfg.get("env", "dev")),
        "BaseURL": str(cfg.get("base_url", "")),
        "Python": platform.python_version(),
        "OS": f"{platform.system()} {platform.release()}",
        "Allure": av,
        "GeneratedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if extra:
        info.update({k: str(v) for k, v in extra.items()})
    lines = [f"{k}={v}" for k, v in info.items() if v not in ("", None)]
    (ad / "environment.properties").write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_report(allure_dir: str = str(ALLURE_RESULTS_DIR),
                    report_dir: str = str(ALLURE_REPORT_DIR),
                    open_report: bool = False) -> int:
    """生成 Allure HTML 报告；返回 0 成功、非 0 失败（前置缺失/生成失败如实返回）。"""
    bin_path = _allure_bin()
    if not bin_path:
        try:
            sys.stderr.write(
                "未生成 Allure 报告：未检测到 allure-commandline（需 Java JRE/JDK 8+ 且 allure 可执行）。\n"
                "  - Node:    npm install -g allure-commandline\n"
                "  - Windows: scoop install allure / choco install allure-commandline / winget install qameta.allure\n"
                "  - macOS:   brew install allure\n"
                "  - Linux:   sudo apt install allure\n"
                "  - 或设置环境变量 ALLURE_BIN 指向 allure 可执行文件\n")
        except UnicodeEncodeError:
            sys.stderr.write(
                "Allure report NOT generated: allure-commandline missing (needs Java + allure CLI).\n")
        return 1
    history_src = Path(report_dir) / "history"
    if history_src.is_dir():  # 复用历史 -> 报告带趋势(trend)/分类/重试视图
        shutil.copytree(history_src, Path(allure_dir) / "history", dirs_exist_ok=True)
    try:  # 写入环境信息（Allure 报告 Environment 控件）
        write_allure_environment(allure_dir)
    except Exception:
        pass
    rc = subprocess.call([bin_path, "generate", allure_dir, "-o", report_dir, "--clean"])
    if rc != 0:
        sys.stderr.write(f"allure generate 失败 rc={rc}\n")
        return rc
    if open_report:
        # 已打开则跳过重新打开，刷新浏览器即可看到最新结果（避免重复起服务/端口冲突）
        if _allure_report_already_open():
            try:
                sys.stdout.write(
                    "Allure 报告已在打开（端口 4040 已占用）：跳过重新打开，刷新浏览器即可查看最新结果。\n")
            except Exception:
                pass
        else:
            # 禁止 file:// 直开；优先 allure open（自带 HTTP 服务）；脱离进程树启动，避免随 pytest 退出被回收
            _open_report_detached(bin_path, report_dir)
    return 0


_ALLURE_PORT = 4040  # 报告服务固定端口：打开与探测都用它，避免自增变化


def _allure_report_already_open(host: str = "127.0.0.1",
                                port: int = _ALLURE_PORT) -> bool:
    """判断 allure 报告服务是否已在本机固定端口监听，避免重复打开。

    仅做 TCP 连通性探测：能连上即视为已有服务在跑，直接复用、刷新即可。
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def _open_report_detached(bin_path: str, report_dir: str,
                          port: int = _ALLURE_PORT) -> None:
    """以脱离父进程树的方式启动 allure open（固定端口），使本地报告服务在 pytest 退出后仍存活。"""
    kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen([bin_path, "open", "--port", str(port), report_dir], **kwargs)
    except Exception:
        pass
```

---

## 一、文件结构（仅 YAML）

### ① 单 API 定义文件（`testcases/apis/`，可复用组件，不直接收集）
一个文件 = 一个 API，自包含 `request` + `extract`/`extract_global` + `validate`。放在 `apis/` 下作为可复用组件；同结构文件放 `testcases/` 非 `apis/` 目录则作为独立单 API 用例被直接收集。

```yaml
# testcases/apis/your_api.yaml —— 单 API 模板
name: <api_name>
request:
  method: <http_method>              # 引用 data/share.yaml 的方法常量（勿硬编码 post/get）
  url: /<resource>/<action>                        # 相对路径；完整地址由 config.yaml 的 base_url 前缀拼接（ApiClient）
  json: { <field>: <value> }                   # 服务端要 JSON 时用 json:；要表单用 form:
extract_global:                     # 跨业务共享（下游步骤/业务用 ${<shared_var>} 取；跨 case 用 ${read_yaml(name)}）
  <shared_var>: [json, $.data.<field>, <default>]
validate:                           # 多类型软断言（失败汇总）
  - equals:      { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }   # 注意 "${}" 在 flow 映射内必须加引号
  - status_code: { name: <断言说明>, expected: 200 }
```

### ② 业务编排文件（`testcases/flows/`，一个文件 = 一个 case）
`steps` 按顺序引用多个单 API 文件（或嵌套另一份 `flows/` 业务），复用其定义；每个 step 可附加 `with`（覆盖本次调用的 request 及 validate/extract）。

```yaml
# testcases/flows/your_flow.yaml —— 业务模板
title: <flow_title>
steps:                              # 业务 = 多个单 API / 子业务组合（顺序执行）
  - include: apis/your_api.yaml
  - include: apis/your_api.yaml
    with:
      json: { <field>: <value> }               # 覆盖请求体
      validate:                     # 覆盖断言（正向/反向用例复用同一定义）
        - not_equals: { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }
  # - include: flows/your_sub_flow.yaml    # 嵌套业务，递归展开为 父业务::子业务::API
```

- `steps` 每项：字符串即 `include` 路径；或 dict `{ include, name?, with? }`。`include` 可指向 `apis/` 单 API 文件，也可指向另一份 `flows/` 业务文件（嵌套业务，递归展开）。
- `include` 解析优先级：业务文件目录下的 `apis/`/`flows/` → 全局 `testcases/apis/`/`testcases/flows/` → 业务文件相对路径。
- `with`：深度合并进被引用文件的 spec——覆盖 `request`（`json`/`params`/`headers`，不覆盖 `method`/`url`）**以及** `validate`/`extract`/`extract_global`（覆盖本次调用的断言与提取，便于同一份定义衍生正向/反向用例）。
- 业务级 `feature`/`story`/`title` 继承给各 step 生成的 Item；嵌套业务的 title 以 `父业务 :: 子业务` 形式体现。

---

## 二、字段语义

### 单 API 文件顶层
| 字段 | 说明 |
| --- | --- |
| `name` | API 名（Item 名组成部分） |
| `request` | 必填：method/url/path/params/query/headers + 请求体（`json`/`form`/`data`/`files` 四选一，见第十一节） |
| `extract` | 提取规则（本业务可见） |
| `extract_global` | 提取规则（跨业务全局共享） |
| `validate` | 断言列表（多类型 + 软断言，见第三节） |

### 业务编排文件顶层
| 字段 | 说明 |
| --- | --- |
| `feature` / `story` / `title` | 业务级元信息（title 标识业务） |
| `steps` | 必填：引用多个单 API 文件（列表） |

### steps[].include / with
| 字段 | 说明 |
| --- | --- |
| `include` | 被引用的单 API 文件（`apis/`）或另一份业务文件（`flows/`，嵌套业务）路径 |
| `name` | 可选，覆盖该次调用的 API 显示名 |
| `with` | 可选，深度合并进被引用文件的 spec：覆盖 `request`（`json`/`params`/`headers`）**及** `validate`/`extract`/`extract_global` |

### extract / extract_global
- `key: $.data.code`（JSONPath）或 `key: [json, $.code, 0]`（带默认值，**字段缺失或无匹配时取默认值**）。
- `extract` 仅本业务可见；`extract_global` 写入全局上下文，跨业务共享。同一业务内上游 API 写入的值对下游 API 直接可见（文件级上下文）。



---

## 三、断言（validate · 多类型 · 软断言）

`validate` 是**断言列表**，每个元素唯一键为**断言类型**，值为参数：

```yaml
validate:
  - equals:        { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }
  - status_code:   { name: <断言说明>, expected: 200 }            # actual 隐含为响应状态码
  - greater_than:  { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }
  - not_equals:    { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }
  - contains:      { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }
  - not_contains:  { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }
  - in:            { name: <断言说明>, actual: $.data.<field>, expected: [<v1>, <v2>] }
  - not_in:        { name: <断言说明>, actual: $.data.<field>, expected: [<v1>] }
  - length:        { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }
  - min_length:    { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }
  - max_length:    { name: <断言说明>, actual: $.data.<field>, expected: <expected_value> }
  - type:          { name: <断言说明>, actual: $.data.<field>, expected: <type> }
  - regex:         { name: <断言说明>, actual: $.data.<field>, pattern: "^1[3-9]\\d{9}$" }
  - exists:        { name: <断言说明>, actual: $.data.<field> }         # 存在且非空
  - not_exists:    { name: <断言说明>, actual: $.data.<field> }           # 不存在或为空
  - schema:        { name: <断言说明>, actual: $, schema: { type: object, required: [<field1>, <field2>] } }
```
> 单个断言也可直接写成一个 dict（非列表），引擎视为单元素列表。`name` 写清「校验什么」，错误时直接展示。

### actual 表达式文法（与模板同文法）
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
| `greater_than` / `gt` | 大于 | `actual`,`expected` |
| `less_than` / `lt` | 小于 | `actual`,`expected` |
| `greater_or_equal` / `gte` | ≥ | `actual`,`expected` |
| `less_or_equal` / `lte` | ≤ | `actual`,`expected` |
| `contains` | 包含（str⊇sub / item∈list / key∈dict） | `actual`,`expected` |
| `not_contains` | 不包含 | `actual`,`expected` |
| `in` | 属于集合 | `actual`,`expected`(列表) |
| `not_in` | 不属于集合 | `actual`,`expected`(列表) |
| `length` | 长度等于 | `actual`,`expected` |
| `min_length` | 长度 ≥ | `actual`,`expected` |
| `max_length` | 长度 ≤ | `actual`,`expected` |
| `type` | 类型检查 | `actual`,`expected`(`str`/`int`/`float`/`bool`/`list`/`dict`/`null`) |
| `regex` / `matches` | 正则匹配 | `actual`,`pattern` |
| `exists` | 存在且非空 | `actual` |
| `not_exists` | 不存在或为空 | `actual` |
| `schema` | JSON Schema 校验 | `actual`,`schema` |
| `status_code` / `status` | 状态码等于 | `expected`（actual 隐含） |

> **别名必须显式分派**：`status_code`/`status` 不是独立比较逻辑，而是「actual 隐含为 `resp.status_code` 的 `equals`」。
> 实现时 `_check` 必须把它映射到 equals 分支（见 §六），否则会命中「未知断言类型」兜底分支，
> 表现为「HTTP 明明 200 却断言失败」，且错误信息是 `未知断言类型 'status_code'`。
> 同理 `eq/ne/gt/lt/gte/lte/matches` 也需按别名分派，避免同类假失败。

### 软断言（API 内）
一个 API 内**所有断言都会执行**，不遇错即停；全部跑完后若有失败，抛出**汇总** `AssertionError`，逐条列出类型、名称、期望值、实际值、取值路径。

### 业务链路硬停止（API 间）⚠️
同一业务（flow）内，若某 API 失败（断言汇总失败 / 请求异常），**立即停止后续 API**，后续标记为 `skipped` 并指向失败上游。错误信息聚焦第一个出错的 API。

### 错误信息格式
```
❌ 业务「<flow_title>」· API「<api_name>」断言失败：共 N 项未通过
  1. [equals · <断言说明>] 期望 == '<expected>' (str) | 实际 '<actual>' (str)  （取值: 响应 $.data.<field>）
  2. [greater_than · <断言说明>] 期望 > <expected> (int) | 实际 <actual> (int)  （取值: 响应 $.data.<field>）
```

> executor 在断言/请求失败时，还会在日志（`Captured log call`）打印该 API 的完整现场 dump（请求/响应/头/体，敏感字段经 `utils.redact` 脱敏），与 Allure 证据一致：
```
接口[<api_name>]
  请求: <method> <base_url><url>
    头: {'Content-Type': 'application/json', 'Authorization': '***'}
    体: {'<field>': '<value>', 'password': '***'}
  响应: HTTP <status> (<ms>ms)
    头: {'Server': 'nginx', ...}
    体: {'code': '<actual>', 'msg': '...', 'data': None}
  错误: ❌ 业务「<flow_title>」· API「<api_name>」断言失败：共 N 项未通过
  1. [equals · <断言说明>] 期望 == '<expected>' (str) | 实际 '<actual>' (str)  （取值: 响应 $.data.<field>）
```

```
❌ 业务「<flow_title>」· API「<api_name>」请求失败：<method> <url> 连接超时 (ConnectionError)
```
```
⏭️  API「<api_name>」已跳过：上游 API『<api_name>』执行失败，已停止执行本业务后续 API
```

---

## 四、模板与变量（utils/templating.py）

`resolve(value, ctx)` 递归渲染 `${...}`：`${var}` / `${env.X}` / `${env(X)}` / `${context.X}` / `${read_yaml(X)}`（最后者与 `${X}` 等价）。`status_code` 是断言专用关键字。变量查找顺序：`ctx.data（运行时 extract/extract_global）` → `常量命名空间（data/ 环境合并后）` → 未命中保留原样/报错。

- **整值替换**：字段整体即 `${x}`（非字符串内嵌）时，返回解析出的对象（dict/list/标量），而非做字符串拼接。
- **引号注意**：`${...}` 出现在行内 flow mapping（花括号 `{ ... }`）的值中时，必须加引号（如 `expected: "${expect.success_code}"`），否则 YAML 会把内部的 `{` 当作嵌套 flow mapping 而解析失败。
- **递归渲染**：`value` 为 dict/list 时递归其每个元素，使 `headers`/`json` 内部的值也能用 `${...}`。
- `method` 字段同样经 `resolve` 解析（见第九节）。

### utils/ 模块源码（单一真相源，原样写入）

**`utils/dicts.py`**：
```python
# -*- coding: utf-8 -*-
"""字典深合并（executor 与 data_loader 共用）。"""


def deep_merge(base: dict, override: dict) -> dict:
    """返回 base 与 override 的深合并结果（不修改入参）；override 中同键覆盖 base，dict 递归合并，其余直接覆盖。"""
    result = dict(base)
    for k, v in (override or {}).items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result
```

**`utils/extract.py`**：
```python
# -*- coding: utf-8 -*-
"""JSONPath 提取（带默认值）。"""
from typing import Any, Tuple

try:
    from jsonpath_ng import parse as _jp_parse
except ImportError:  # pragma: no cover
    _jp_parse = None  # type: ignore


def parse_extract(val) -> Tuple[str, Any, Any]:
    """解析 extract/extract_global 规则。
    - 列表形式: [mode, path, default]，如 [json, $.data.id, ""]
    - 字符串形式: 视为 [json, path, None]
    返回 (mode, path, default)。
    """
    if isinstance(val, list):
        mode = str(val[0]).lower() if len(val) > 0 else "json"
        path = val[1] if len(val) > 1 else None
        default = val[2] if len(val) > 2 else None
        return mode, path, default
    return "json", val, None


def jsonpath_extract(data: Any, expr: str, default: Any = None) -> Any:
    """对 data 用 JSONPath 取值；无匹配或解析失败返回 default。"""
    if _jp_parse is None:  # pragma: no cover
        raise RuntimeError("jsonpath-ng 未安装，请 pip install -r requirements.txt")
    if data is None:
        return default
    try:
        matches = [m.value for m in _jp_parse(expr).find(data)]
    except Exception:
        return default
    if not matches:
        return default
    return matches[0] if len(matches) == 1 else matches
```

**`utils/templating.py`**：
```python
# -*- coding: utf-8 -*-
"""${var} / ${env.X} / ${context.X} / ${read_yaml(X)} 模板解析。
变量查找顺序：运行时变量(ctx) → 常量命名空间(data/ 环境合并后) → 未命中保留原样。
"""
import os
import re
from typing import Any, Dict, Optional

_VAR = re.compile(r"\$\{([^}]+)\}")

_CONSTANTS: Dict[str, Any] = {}


def set_constants(ns: Optional[Dict[str, Any]]) -> None:
    """注入当前环境常量命名空间（由 conftest 在会话开始时调用）。"""
    global _CONSTANTS
    _CONSTANTS = ns or {}


def get_constants() -> Dict[str, Any]:
    return _CONSTANTS


def _as_runtime(ctx) -> Dict[str, Any]:
    """把 ctx（dict 或 ApiContext）归一为运行时变量字典。"""
    if isinstance(ctx, dict):
        return ctx
    runtime = getattr(ctx, "runtime", None)
    if callable(runtime):
        return runtime()
    data = getattr(ctx, "data", None)
    return data if isinstance(data, dict) else {}


def _lookup(name: str, runtime: Dict[str, Any]) -> Any:
    name = name.strip()
    # ${env.X} / ${env(X)}
    if name.startswith("env."):
        return os.environ.get(name[4:])
    if name.startswith("env("):
        return os.environ.get(name[4:].rstrip(")"))
    if name.startswith("context."):
        return runtime.get(name[8:])
    # ${read_yaml(X)} 等价于 ${X}（运行时变量）
    if name.startswith("read_yaml("):
        name = name[len("read_yaml("):].rstrip(")")

    # 优先运行时变量（含 extract_global）
    if name in runtime:
        return runtime[name]
    # 嵌套路径逐段查找运行时变量
    cur = runtime
    ok = True
    for part in name.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            ok = False
            break
    if ok:
        return cur
    # 回退到常量命名空间
    cur = _CONSTANTS
    ok = True
    for part in name.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            ok = False
            break
    if ok:
        return cur
    # 未命中：保留原样（便于排障）
    return "${" + name + "}"


def _resolve_str(s: str, runtime: Dict[str, Any]) -> Any:
    s = str(s)
    m = _VAR.fullmatch(s.strip())
    if m:
        return _lookup(m.group(1), runtime)        # 整值替换：返回对象（dict/list/标量）
    return _VAR.sub(lambda mm: str(_lookup(mm.group(1), runtime)), s)


def resolve(value: Any, ctx: Any) -> Any:
    """递归渲染 ${...}。dict/list 递归；字符串按整值或内嵌替换。"""
    if isinstance(value, str):
        return _resolve_str(value, _as_runtime(ctx))
    if isinstance(value, dict):
        return {k: resolve(v, ctx) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(resolve(v, ctx) for v in value)
    return value
```

---

## 五、请求会话（common/request_client.py）

- `ApiResponse`：`status_code`/`json`/`text`/`elapsed_ms`/`headers`/`request_path`。
- `ApiClient(base_url, timeout, retries, headers, verify)` 持有 `requests.Session`；公共默认请求头由 executor 从 `data/share.yaml` 的 `default_headers` 注入并作为默认层。`request(method, path, **kw)`：`path` 绝对地址直接用，否则 `base_url + path`；发送前合并 `默认头 + kw.headers`（kw 同名头覆盖默认头）；再写入 `Authorization`（已有不覆盖）；连接错误/超时重试 `retries` 次（HTTP 4xx 不重试）；捕获 `requests.RequestException` 脱敏后抛 `ApiExecError`（含方法/路径/异常类型）；返回前用标准库 `logging.getLogger("api.client")` 记录。
- `ApiExecError(Exception)`：请求级失败，触发业务链路硬停止。

### common/request_client.py 源码（单一真相源，原样写入）

```python
# -*- coding: utf-8 -*-
"""请求会话：封装 requests.Session，负责 URL 拼接、默认头合并、Token 注入、重试与异常脱敏。"""
import time
from typing import Any, Dict, Optional

try:
    import requests
    from requests.exceptions import RequestException
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

import logging
from utils.redact import redact

log = logging.getLogger("api.client")


class ApiExecError(Exception):
    """请求级失败，触发业务链路硬停止。"""


class ApiResponse:
    """对单次 HTTP 响应的轻封装。"""

    def __init__(self, status_code: int, json_body: Any, text: str,
                 elapsed_ms: float, headers: Dict[str, str], request_path: str) -> None:
        self.status_code = status_code
        self.json = json_body
        self.text = text
        self.elapsed_ms = elapsed_ms
        self.headers = headers
        self.request_path = request_path


class ApiClient:
    """持有 requests.Session；对外仅此一处发请求（鉴权单点在此）。"""

    def __init__(self, base_url: str, timeout: int = 30, retries: int = 1,
                 headers: Optional[Dict[str, str]] = None, verify: bool = True,
                 token: Optional[str] = None) -> None:
        if requests is None:  # pragma: no cover
            raise RuntimeError("requests 未安装，请执行 pip install -r requirements.txt")
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self.retries = max(0, int(retries))
        self.default_headers = dict(headers or {})
        self.verify = verify
        self.token = token
        self._session = requests.Session()

    def request(self, method: str, path: str, **kwargs) -> ApiResponse:
        url = path if str(path).startswith(("http://", "https://")) else f"{self.base_url}{path}"
        # 合并默认头 + 本次请求头（本次同名覆盖默认头）
        headers = dict(self.default_headers)
        headers.update({k: str(v) for k, v in (kwargs.pop("headers", None) or {}).items()})
        # 鉴权单点：仅在尚未设置 Authorization 时注入
        if self.token and "Authorization" not in headers:
            headers["Authorization"] = str(self.token)
        attempt = 0
        last_err: Optional[Exception] = None
        while attempt <= self.retries:
            try:
                resp = self._session.request(
                    method, url, headers=headers, timeout=self.timeout,
                    verify=self.verify, **kwargs)
                try:
                    body = resp.json()
                except ValueError:
                    body = None
                result = ApiResponse(
                    status_code=resp.status_code, json_body=body, text=resp.text,
                    elapsed_ms=round(resp.elapsed.total_seconds() * 1000, 2),
                    headers=dict(resp.headers), request_path=path)
                log.info("→ %s %s | HTTP %s | %sms", method, path, resp.status_code, result.elapsed_ms)
                return result
            except RequestException as e:
                last_err = e
                # 连接错误/超时重试；HTTP 4xx/5xx 不重试（已进入上面的分支）
                if attempt >= self.retries:
                    break
                attempt += 1
                time.sleep(0.5)
        # 脱敏后抛 ApiExecError（不泄露敏感头）
        safe_headers = redact(dict(headers))
        raise ApiExecError(
            f"{method} {path} 请求失败 ({type(last_err).__name__}: {last_err}) | headers={safe_headers}")
```

---

## 六、断言引擎（common/assert_utils.py）

```python
class ApiExecError(Exception): ...

_STATUS_ALIASES = ("status_code", "status")     # 状态码断言：actual 隐含为 resp.status_code

def assert_spec(resp, validate, ctx, *, api_name="", biz_title="") -> None:
    from utils.templating import resolve
    specs = _normalize_validate(validate)        # -> [(type, spec)]
    failures = []
    for atype, raw in specs:
        spec = dict(raw) if isinstance(raw, dict) else {}
        for key in ("expected", "pattern"):      # expected/pattern 支持 ${...} 常量（如 expected: "${expect.success_code}"）
            if key in spec:
                spec[key] = resolve(spec[key], ctx)
        # ⚠️ status_code/status 无 actual 时，actual 隐含为响应状态码（勿走 _resolve_actual）
        if str(atype).strip().lower() in _STATUS_ALIASES and "actual" not in spec:
            actual, src = resp.status_code, "响应状态码"
        else:
            actual, src = _resolve_actual(spec.get("actual"), resp, ctx)  # src=取值说明（actual 专门解析，勿在此渲染）
        try:
            _check(atype, actual, spec, resp, ctx)
        except AssertionError as e:
            failures.append((atype, spec.get("name", atype), str(e), src))
    if failures:
        raise AssertionError(_format_summary(biz_title, api_name, failures))


def _format_summary(biz_title: str, api_name: str, failures) -> str:
    """按第三节格式汇总断言失败：业务/接口标题 + 编号列表（类型·名称·期望|实际·取值路径）。"""
    lines = [f"❌ 业务「{biz_title}」· API「{api_name}」断言失败：共 {len(failures)} 项未通过"]
    for i, (atype, name, err, src) in enumerate(failures, 1):
        lines.append(f"  {i}. [{atype} · {name}] {err}  （取值: {src}）")
    return "\n".join(lines)
```
- `_resolve_actual` 返回 `(值, 取值说明)`，错误信息展示「取值: 响应 $.code」。
- `_check` 按类型比较，失败抛 `AssertionError`（自带「期望 X | 实际 Y」与类型语义）。
- **⚠️ `_check` 必须先做别名归一化再分支**（漏此步 = 「HTTP 200 却断言失败」的假失败）：

```python
def _check(atype, actual, spec, resp=None, ctx=None) -> None:
    at = str(atype).strip().lower()
    expected = spec.get("expected")
    # ① status_code / status -> equals（actual 已由 assert_spec 置为 resp.status_code）
    if at in _STATUS_ALIASES:
        at = "equals"
    # ② 其余别名：eq->equals / ne->not_equals / gt->greater_than / lt->less_than
    #    gte->greater_or_equal / lte->less_or_equal / matches->regex
    at = _ALIAS.get(at, at)
    ...
    else:
        _fail(f"未知断言类型 {atype!r}")   # 兜底；正常路径不应到达
```
  自检要求：写一个只含 `- status_code: { expected: 200 }` 的用例跑真实 200 响应，**必须通过**；
  若报 `未知断言类型 'status_code'`，即分派缺失。
- `_format_summary` 输出第三节格式。`equals` 数值宽松转换（`"200"` 与 `200` 判等）；`type` 字符串映射 Python 类型；`schema` 用 `jsonschema.validate`；`regex` 用 `re` 匹配。
- `_resolve_actual` 对 `$.x` 取值时，若 `resp.json` 为 `None`（如 404/405 返回 HTML），错误信息须明确提示「响应非 JSON（HTTP {status}，可能路径或方法不符），无法按 JSONPath 取值」，而非只报「实际 None」，便于快速定位路径/方法错误。
- `assert_spec` 先用 `resolve()` 渲染每个断言的 `expected`/`pattern`（支持 `${...}` 常量）；`actual` 交由 `_resolve_actual` 专门解析，二者不重复处理——这保证 `expected: "${expect.success_code}"` 等常量化预期值能正确生效。

---

## 七、执行引擎（engine/executor.py）

```python
from utils.redact import redact


def _fmt_req(client, method, target, headers, params, body) -> str:
    full = f"{client.base_url}{target}" if client else target
    lines = [f"  请求: {method} {full}"]
    if headers:
        lines.append(f"    头: {redact(headers)}")
    if params:
        lines.append(f"    参数: {params}")
    if body is not None:
        lines.append(f"    体: {redact(body)}")
    return "\n".join(lines)


def _fmt_resp(resp) -> str:
    if resp is None:
        return "  响应: (无，请求未成功)"
    lines = [f"  响应: HTTP {resp.status_code} ({resp.elapsed_ms}ms)"]
    if resp.headers:
        lines.append(f"    头: {redact(dict(resp.headers))}")
    body = resp.json if resp.json is not None else resp.text
    if body:
        lines.append(f"    体: {redact(body)}")
    return "\n".join(lines)


def _format_failure(api_name, client, method, target, headers, params, body, resp, error):
    """组装可读的失败现场（接口 + 请求 + 响应 + 错误），供日志与 Allure 共用。"""
    return (f"接口[{api_name}]\n"
            f"{_fmt_req(client, method, target, headers, params, body)}\n"
            f"{_fmt_resp(resp)}\n"
            f"  错误: {error}")


def build_step_spec(step, base_dir, apis_dir):
    if isinstance(step, str):
        step = {"include": step}
    path = _resolve_api_path(step["include"], base_dir, apis_dir)
    api = load_case(path)                        # 单 API 定义（嵌套 flow 由 collector 递归展开）
    spec = dict(api)
    if "name" in step:    spec["name"] = step["name"]
    if "with" in step:
        w = step["with"]
        spec["request"] = deep_merge(api.get("request", {}), w)   # 覆盖 json/params/headers（deep_merge 来自 utils.dicts，data_loader 亦复用，避免重复定义）
        for k in ("validate", "extract", "extract_global"):        # 覆盖断言/提取（正向/反向复用）
            if k in w:
                spec[k] = w[k]
    return spec

def _save_evidence(api_name, *, request=None, response=None, error=None, detail=None):
    """失败现场留证：请求/响应快照写入 artifacts/ 并挂载 Allure（含可读文本）。"""
    import json as _json, time as _t
    from pathlib import Path
    from engine.reporting.report import attach_failure_artifact, attach_failure_text
    art_dir = ARTIFACTS_DIR; art_dir.mkdir(exist_ok=True)
    snap = {"api": api_name, "request": request, "response": response, "error": error}
    path = art_dir / f"{api_name}__{_t.strftime('%H%M%S', _t.localtime())}.json"
    try:
        path.write_text(_json.dumps(snap, ensure_ascii=False, default=str), encoding="utf-8")
        attach_failure_artifact(f"失败证据-{api_name}", str(path))   # 挂载到 Allure，可回溯
    except Exception:
        pass
    if detail:
        try:
            attach_failure_text(f"失败详情-{api_name}", detail)
        except Exception:
            pass

def _run_single_api(client, api_spec, ctx):
    req = api_spec.get("request", {}) or {}
    method = normalize_method(resolve(req.get("method"), ctx.data))   # 解析 + 规范化（method 经 data/ 常量解析）
    target = resolve(req.get("url") or req.get("path") or "", ctx.data)
    headers = resolve(req.get("headers", {}), ctx.data)
    params  = resolve(req.get("params") or req.get("query") or {}, ctx.data)
    json_body = resolve(req.get("json"), ctx.data) or None                                   # application/json
    form_body = resolve(req.get("form") or req.get("data"), ctx.data) or None                # x-www-form-urlencoded
    files_body = resolve(req.get("files"), ctx.data) or None                                 # multipart/form-data
    body_payload = json_body if json_body is not None else form_body
    api_name = api_spec.get("name", target)
    with allure.step(f"{method} {target} [{api_name}]"):   # trace：每个 API 成为 Allure step，失败可展开调用链
        try:
            resp = client.request(method, target, json=json_body, data=form_body,
                                  files=files_body, params=params, headers=headers)
        except RequestException as e:
            detail = _format_failure(api_name, client, method, target, headers,
                                     params, body_payload, None,
                                     f"{type(e).__name__}: {e}")
            _save_evidence(api_name, request={"method": method, "url": f"{client.base_url}{target}",
                                              "headers": redact(headers), "params": params,
                                              "body": redact(body_payload)},
                          error=f"{type(e).__name__}: {e}", detail=detail)   # 请求失败也留证
            err = ApiExecError(f"请求失败：{method} {target} - {type(e).__name__}: {e}")
            setattr(err, "details", detail)
            raise err from e
        # parse_extract 返回 3 元组 (mode, path, default)；调用处必须按 3 元组解包
        # （历史上曾误写成 `jp, default = parse_extract(val)`，只要出现 extract/extract_global
        #  就抛 `too many values to unpack (expected 2)`，务必保持 mode 占位）
        for key, val in (api_spec.get("extract") or {}).items():
            _mode, jp, default = parse_extract(val); ctx.set(key, extract(resp.json, jp, default))
        for key, val in (api_spec.get("extract_global") or {}).items():
            _mode, jp, default = parse_extract(val); ctx.set_global(key, extract(resp.json, jp, default))
        try:
            assert_spec(resp, api_spec.get("validate") or [], ctx.data,
                        api_name=api_name, biz_title=ctx.biz_title)
        except AssertionError as e:
            detail = _format_failure(api_name, client, method, target, headers,
                                     params, body_payload, resp, str(e))
            _save_evidence(api_name, response={"status": resp.status_code,
                                              "elapsed_ms": resp.elapsed_ms,
                                              "headers": redact(dict(resp.headers)),
                                              "json": redact(resp.json), "text": resp.text[:2000]},
                          error=str(e), detail=detail)
            setattr(e, "details", detail)
            raise

def _flatten_steps(case, base_dir, apis_dir):
    """把 steps（含嵌套 flow include）展开为有序单 API spec 列表——一个 flow 即一个 case 的全部步骤。"""
    out = []
    for step in (case.get("steps") or []):
        if isinstance(step, str):
            step = {"include": step}
        path = _resolve_api_path(step["include"], base_dir, apis_dir)
        included = load_case(path)
        if included.get("steps"):                     # 嵌套业务：递归展开并入本 case
            out.extend(_flatten_steps(included, path.parent, apis_dir))
        else:
            out.append(build_step_spec(step, base_dir, apis_dir))
    return out

def run_flow(client, case, ctx, log=None):
    steps = _flatten_steps(case, ctx.base_dir, ctx.apis_dir)
    if not steps:
        raise ValueError(f"业务 {case.get('title') or case.get('name')} 缺少 steps")
    total = len(steps)
    for i, spec in enumerate(steps, 1):
        req = spec.get("request", {}) or {}
        method = normalize_method(resolve(req.get("method"), ctx.data))
        target = resolve(req.get("url") or req.get("path") or "", ctx.data)
        api_name = spec.get("name", target)
        if log:
            log.info("步骤 %d/%d · %s %s [%s]", i, total, method, target, api_name)   # 日志含步骤
        try:
            _run_single_api(client, spec, ctx)       # 内部 allure.step + 软断言 + 失败留证
        except (AssertionError, ApiExecError) as e:
            if log:
                detail = getattr(e, "details", None) or str(e)
                log.error("步骤 %d/%d 失败，硬停止后续步骤 [%s]\n%s", i, total, api_name, detail)
            raise                                     # 任一步骤失败 → 本 case 失败，后续步骤不再执行
        if log:
            log.info("步骤 %d/%d 通过 [%s]", i, total, api_name)
```
- **一个 business flow = 一个 case**：`run_flow` 顺序执行该 flow 展开后的全部步骤；每个 API 包为 `allure.step`（报告呈现实步骤树），并写入日志「步骤 i/n · METHOD url [name] → 通过/失败」，**日志与报告中均有步骤**。
- **失败保留证据**：断言失败 / 请求异常时，`_save_evidence` 把请求与响应快照写入 `artifacts/` 并通过 `engine.reporting.report.attach_failure_artifact` 挂载到 Allure（UI 方向在 `_save_evidence` 处额外 `allure.attach` 截图），失败现场可回溯；`artifacts/` 由 `.gitignore` 排除。
- 业务内上下文 `ctx` 在 `steps` 执行期持续存在：上游 `extract`/`extract_global` 对下游直接可见。
- 跨业务共享依赖 `ApiContext._GLOBAL`（模块级）；每文件独立 `ApiContext`（局部）实例。

---

## 八、收集器（engine/collector.py，pytest 自动收集 · 一个 business flow = 一个 case）

```python
def pytest_collect_file(parent, file_path):
    p = Path(file_path)
    if p.suffix.lower() not in (".yaml", ".yml"): return None   # 仅 YAML
    if "testcases" not in p.parts: return None
    if p.parent.name == "apis": return None          # 库目录不直接收集
    try: _case = load_case(p)
    except Exception: _case = {}
    if _case.get("component") or _case.get("reusable"):
        return None                                   # 仅被 include 的业务，不独立收集
    return YamlFile.from_parent(parent, path=p)

class YamlFile(pytest.File):
    def collect(self):
        case = load_case(self.path)
        title = case.get("title") or case.get("name") or self.path.stem
        spec = dict(case); spec["__title__"] = title
        # 一个 business flow = 一个 case：单个 ApiItem，steps 在 runtest 内顺序执行
        yield ApiItem.from_parent(self, name=title, spec=spec)

class ApiItem(pytest.Item):
    def __init__(self, name, parent, **kwargs):
        self.spec = kwargs.pop("spec")
        super().__init__(name=name, parent=parent, **kwargs)
    def runtest(self):
        base_url = _resolve_env(self.spec)   # 从 config.yaml 读 base_url；缺失即抛配置错误（不收集/不 skip）
        client = ApiClient(base_url, token=get_config("config/config.yaml").get("token"))
        ctx = ApiContext(biz_title=self.spec.get("__title__"),
                         base_dir=self.parent.path.parent, apis_dir=_find_apis_dir(self.parent.path))
        run_flow(client, self.spec, ctx, log=logging.getLogger("engine.flow"))   # 一个 case 内顺序执行全部步骤
```

- **一个 business flow = 一个 case**：每个 `flows/` 文件收集为**一个** `ApiItem`，Item 名 = flow 的 `title`；其 `steps`（含嵌套 flow，由 `_flatten_steps` 展开）在 `runtest` 内经 `run_flow` 顺序执行。
- **步骤可见**：每个 API 包为 `allure.step`（报告步骤树），并写日志「步骤 i/n · METHOD url [name] → 通过/失败」。
- **业务内硬停止**：任一步骤断言失败/请求异常 → 该 case 失败，后续步骤不再执行（在 `run_flow` 内中断）。
- `apis/` 库目录文件**不收集**；只在被 `flows/` 引用时执行。被复用、不应独立执行的业务文件顶部加 `component: true`。
- 一个 case 的全部步骤在同一 Item 内执行，天然落在同一 worker，**变量传递与硬停止不受并行影响**（`--dist loadscope` 双保险）；`extract_global` 仍为进程级、跨 case 不互通。

---

## 九、数据复用（常量 / 环境 Profile）

数据与结构分离：**用例 YAML 只写结构/逻辑，具体值用 `${...}` 引用 `data/` 中的常量**，实现集中管控与多环境复用。

### 外部化原则（能用常量替代的就替代）
- **具体值默认全部外部化到 `data/`**：HTTP method、URL、请求头、请求体、预期业务码/状态码等**跨环境一致**的值在 `data/share.yaml` 定义为常量；**账号密码/token 等环境专属的敏感值不放 `share.yaml`，改放 `data/<env>.yaml`**（见下条），由 `env` 深合并覆盖。用例 YAML 通过 `${...}` 引用；**结构与逻辑**（`steps` 编排、`validate` 的断言类型与 `actual` 取值路径、`extract` 规则）留在用例文件。
- **method 用共享方法常量**：`data/share.yaml` 统一定义 `{ GET: get, POST: post, PUT: put, DELETE: delete, PATCH: patch }`，API 里写 `method: "${POST}"`。集中管控、避免大小写/拼写不一致、可全局替换。
- **预期业务码/状态码也外部化**：如 `expect: { success_code: "200", http_ok: 200 }`，断言写 `expected: "${expect.success_code}"`（注意加引号，见第四节）。同一服务端成功码全局一致，改一处即可。
- **账号密码/token 外部化**：放 `data/<env>.yaml`，按环境切换不公用例。
- **默认头**由 `data/share.yaml` 的 `default_headers` 提供（`executor` 合并默认头与 feature/接口头）。

### 目录与文件
```
data/
  share.yaml       # 公共默认数据（methods 方法常量 / expect 预期码 / default_headers 默认头；不含账号密码等环境专属敏感值）
  dev.yaml         # 开发环境覆盖（由 config.yaml 的 env 选择；账号密码等敏感/易变值放这里）
  prod.yaml        # 生产环境覆盖
```
`config/config.yaml` 增加 `env: dev` 选择环境；数据按 `share ⊕ env`（深合并）加载。

**`data/share.yaml` 模板**：
```yaml
# 共享方法常量（API 用 method: "${POST}" 引用）
GET: get
POST: post
PUT: put
DELETE: delete
PATCH: patch
# 预期值常量（断言用 expected: "${expect.success_code}" 引用；注意 flow 映射内加引号）
expect:
  success_code: "200"      # 该服务端成功业务码（多为字符串 "200"；有的服务端是 0，按实际改）
  http_ok: 200
# 全局默认头（executor 作为默认层注入；接口/with 可覆盖同名）
default_headers:
  Content-Type: application/json
# 注：账号密码/token 等环境专属敏感值不要放这里，放 data/<env>.yaml（见下方模板）
```

**`data/dev.yaml` 模板（环境专属覆盖；账号密码/token 等敏感值放这里）**：
```yaml
# 仅开发环境不同的常量；账号密码等敏感值定义在具体环境文件，不在 share.yaml
login:
  valid:
    username: dev_user
    password: dev_pass
# token 等如需覆盖也可放这里
```

### 加载与合并
- 启动时加载 `data/share.yaml`，再按 `env` 深合并 `data/<env>.yaml`，得到「当前环境常量」。
- 常量命名空间作为 `resolve` 的**基础层**：共享方法常量 `${GET}`/`${POST}`、业务数据 `${login.valid.username}`、预期码 `${expect.success_code}`、整段引用（如 `${account.valid}` 直接返回 dict）均可在用例中引用。

### 引用语法与解析要求
- 标量：`${login.valid.username}`；整段（dict/list）：字段整体为 `${login.headers}` 时直接返回该对象（非字符串拼接）。
- `resolve` 必须**递归 dict/list**，使 `headers`/`json` 内部的值也能用 `${...}`。
- `method` 也经 `resolve` 解析后过规范化（`_run_single_api` 中 `method = normalize_method(resolve(req.get("method"), ctx.data))`）。

### 优先级（低 → 高）
`常量(环境合并后) < ctx 运行时(extract_global) < with 字段级覆盖`。

---

## 十、运行入口（scripts/runner.py，pytest 启动器）

`python scripts/runner.py [pytest 参数]`：以 `pytest.main(sys.argv[1:])` 透传参数启动；并行可选，在 `pytest.ini` 的 `addopts` 追加 `-n auto` 即可（依赖 pytest-xdist）。直接 `pytest` 亦可（串行，或自带 `-n`）。日志由 pytest.ini 的 logging 配置驱动（控制台 `log_cli` + 文件 `logs/pytest.log`），每个 API 记为其所属 case 内的一个步骤。

### 入口与 CI 源码（单一真相源，原样写入）

**`conftest.py`**：
```python
# -*- coding: utf-8 -*-
"""会话级配置：常量注入、Allure 报告生成与收尾。失败重试交由 pytest-rerunfailures 负责。"""
import os
import sys

# 确保项目根目录在 sys.path 中（common/engine/utils 顶层可导入）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

pytest_plugins = ["engine.collector"]


def pytest_addoption(parser):
    # 功能开关（与 pytest.ini 对应，环境变量可覆盖，便于 CI 动态开关）
    parser.addini("enable_allure_report", "是否生成 Allure HTML 报告", type="bool", default=True)
    parser.addini("auto_open_report", "生成后是否自动打开", type="bool", default=True)
    parser.addini("enable_email_report", "测试完成后是否发送邮件通知", type="bool", default=False)
    # 环境选择：--env 覆盖 config.yaml 的 env（对应 data/<env>.yaml）
    parser.addoption("--env", action="store", default=None,
                     help="目标环境(dev/prod)，对应 data/<env>.yaml，覆盖 config.yaml 的 env")


# 开关：pytest.ini 值 < 同名环境变量
_ENV_OVERRIDE = {
    "enable_allure_report": "ENABLE_ALLURE_REPORT",
    "auto_open_report": "AUTO_OPEN_REPORT",
    "enable_email_report": "ENABLE_EMAIL_REPORT",
}


def _switch(config, name, cast=str):
    env_key = _ENV_OVERRIDE.get(name)
    if env_key and os.environ.get(env_key) is not None:
        return cast(os.environ[env_key])
    return cast(config.getini(name))


def _bool(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def pytest_configure(config):
    # 注入当前环境常量到模板解析（data/share.yaml ⊕ data/<env>.yaml）
    from common.config_reader import get_config
    from common.data_loader import load_constants
    from utils.templating import set_constants
    # 环境名优先级：--env > 环境变量 TEST_ENV > config.yaml 的 env > "dev"
    env_name = config.getoption("--env", default=None)
    if not env_name:
        env_name = os.environ.get("TEST_ENV")
    if not env_name:
        env_name = get_config("config/config.yaml").get("env", "dev")
    env_name = env_name or "dev"
    set_constants(load_constants(env_name))


def pytest_sessionstart(session):
    from common.context import ApiContext
    from engine.reporting.report import reset_allure_dir
    ApiContext.reset_global()      # 每个会话开始清空跨 case 全局变量，避免进程级污染
    reset_allure_dir(session)


def pytest_sessionfinish(session, exitstatus):
    from engine.reporting.report import finalize_report_session

    auto_open = _switch(session.config, "auto_open_report", _bool)
    report_enabled = _switch(session.config, "enable_allure_report", _bool)
    enable_email = _switch(session.config, "enable_email_report", _bool)
    finalize_report_session(
        session,
        auto_open=auto_open,
        report_enabled=report_enabled,
        enable_email=enable_email,
    )
```

**`scripts/runner.py`**：
```python
# -*- coding: utf-8 -*-
"""pytest 启动器：透传参数给 pytest（并行/重试/报告等开关统一在 pytest.ini 配置）。
用法：python scripts/runner.py [pytest 参数]   例：python scripts/runner.py -k login
如需并行，可在 pytest.ini 的 addopts 加 -n auto，或运行时加 -n auto。
"""
import sys

import pytest


def main():
    return pytest.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
```

**`scripts/run_tests.py`**：
```python
# -*- coding: utf-8 -*-
"""CI/CD 统一入口：清理历史结果 → 按环境跑 pytest →（可选）生成报告/发邮件。

设计目标：本地与 CI 通用；所有行为通过参数或环境变量控制，便于流水线拼装。
复用既有 pytest 开关（ENABLE_ALLURE_REPORT / AUTO_OPEN_REPORT / ENABLE_EMAIL_REPORT）
与环境选择（--env / TEST_ENV / config.yaml 的 env），不重复造轮子。

CI 用法示例：
  python scripts/run_tests.py --env dev
  python scripts/run_tests.py --env prod --email on        # 需注入 MAIL_SMTP_PASSWORD
  python scripts/run_tests.py --env dev -k login -n auto    # 透传 pytest 参数（含并行）
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLURE_RESULTS = ROOT / "allure-results"
REPORT_DIR = ROOT / "reports" / "allure-report"
JUNIT = ROOT / "reports" / "junit.xml"


def _clean() -> None:
    """清空上一次的结果与报告，保证 CI 产物干净、可复现。"""
    for d in (ALLURE_RESULTS, REPORT_DIR):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    ALLURE_RESULTS.mkdir(parents=True, exist_ok=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="API 自动化 CI/CD 入口", allow_abbrev=False)
    p.add_argument("--env", default=None, help="目标环境(dev/prod)，对应 data/<env>.yaml")
    p.add_argument("--open", dest="open_report", action="store_true",
                   help="生成报告后自动打开（CI 默认不打开，无浏览器）")
    p.add_argument("--no-open", dest="open_report", action="store_false")
    p.add_argument("--report/--no-report", dest="report", default=True,
                   help="是否生成 Allure HTML 报告")
    p.add_argument("--email", choices=["on", "off", "auto"], default="auto",
                   help="邮件通知：on 强制开 / off 强制关 / auto 跟随 ENABLE_EMAIL_REPORT")
    p.add_argument("--junit/--no-junit", dest="junit", default=True,
                   help="是否输出 JUnit XML（reports/junit.xml），便于 CI 解析结果")
    p.add_argument("--keep-results", action="store_true",
                   help="不清空 allure-results（默认清空，保证产物干净）")
    p.add_argument("pytest_args", nargs="*",
                   help="透传给 pytest 的额外参数，如 -k login -n auto")
    args = p.parse_args(argv)

    if not args.keep_results:
        _clean()

    # CI 无浏览器：默认关闭自动打开；显式 --open 才打开
    os.environ["AUTO_OPEN_REPORT"] = "true" if args.open_report else "false"
    os.environ["ENABLE_ALLURE_REPORT"] = "true" if args.report else "false"
    if args.email == "on":
        os.environ["ENABLE_EMAIL_REPORT"] = "true"
    elif args.email == "off":
        os.environ["ENABLE_EMAIL_REPORT"] = "false"
    # 环境：优先用 --env；同时写 TEST_ENV 供直接跑 pytest 时复用
    if args.env:
        os.environ["TEST_ENV"] = args.env

    cmd = [sys.executable, "-m", "pytest", "-c", "pytest.ini"]
    if args.junit:
        cmd += [f"--junitxml={JUNIT}"]
    if args.env:
        cmd += ["--env", args.env]
    cmd += args.pytest_args

    rc = subprocess.call(cmd, cwd=str(ROOT))
    print(f"\n[ci] exit={rc}  allure-results={ALLURE_RESULTS}  report={REPORT_DIR}"
          + (f"  junit={JUNIT}" if args.junit else ""))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
```

---

## 十一、常见坑与规避（生成用例/排障必读）

> 下列均为真实项目踩过的坑；生成模板与排障时按此规避。

### 1) 请求体类型：JSON / 表单 / multipart 别选错
- `json:` → `application/json`；`form:`/`data:` → `application/x-www-form-urlencoded`；`files:` → `multipart/form-data`。**用错类型，服务端常返回业务码 `500 未知异常`（HTTP 仍 200）**。
- **排障**：登录/提交类接口若返回"未知异常/系统错误"，优先怀疑体类型——用 Apifox/浏览器 DevTools 看该接口到底收 JSON 还是表单，再把 YAML 的 `json:` 换成 `form:`（或反之）。`form` 与 `json` 同时存在时 `form` 优先生效。
- `files:` 传 multipart：`files: { field: 文件路径 }` 或 `files: { field: [文件名, 内容/路径] }`。

### 2) 业务码常是字符串，别用数字硬比
- 很多服务端成功码是字符串 `"200"`（甚至 `"0"`），不是数字。`equals` 已做**数值宽容**（`"200"` 与 `200` 判等），但**类型/长度类断言**仍看真实类型。
- 预期码统一走常量 `expect.success_code`（在 `data/share.yaml` 定义为字符串），改一处全局生效；flow 映射内写 `expected: "${expect.success_code}"` **必须加引号**。

### 3) 404 / 非 JSON 响应会让 `$.x` 取到 None
- 路径写错 → `404` 返回的是 HTML，`resp.json` 为 `None`，于是 `$.code` 取到 `None`、断言报「实际 None」。**排障**：看状态码是不是 4xx/5xx、URL 与方法是否和服务端一致；框架会对「非 JSON 却按 JSONPath 取值」给出明确提示。
- 405 = 方法不对（GET/POST 用反）；404 = 路径不存在。二者都与 token 无关。

### 4) Token 鉴权：Bearer、裸 token、参数、body 都有可能
- 常见三种：① `Authorization: Bearer <token>`；② `Authorization: <裸token>`（**不加 Bearer**）；③ token 作为查询参数/表单字段。**同一个后端只用其中一种**，用错会返回「未登录/登录失效」。
- **排障**：以 Apifox/DevTools 里能跑通的那次请求为准——看 token 究竟放在 header 还是 body/param、加不加 `Bearer`，再在 YAML 里 1:1 复刻。本框架用 `headers`/`params`/`form`/`json` 均可注入 `${token}`。
- 登录接口用 `extract_global` 把 token 写入全局，下游 API 用 `${token}` 引用（见第四节）。

### 5) 并行（xdist，可选）：用 `--dist loadscope`，且全局变量不跨 worker
- 默认 `--dist load` 会把**同一 flow 的多个步骤拆到不同进程**，导致：变量（`extract`/`extract_global`）丢失、业务内「硬停止」失效（下游不再被 skip）。**必须 `--dist loadscope`**（已固化进 `pytest.ini` 的 `addopts`），让同一 flow 的步骤落在同一 worker。
- `extract_global` 是**进程级**共享：跨 worker 不互通。**跨 flow** 依赖全局变量的链路，要么合并进同一 flow，要么对这类链路串行跑。

### 6) 测试结束后自动生成并打开 Allure 报告
- **结果目录走 pytest.ini**：`addopts` 含 `--alluredir=allure-results`，裸 `pytest`/`python runner.py` 即由 allure-pytest 自动写结果，无需每次传 `--alluredir`。
- **生成 + 打开走 conftest，且开关独立**：`allure-pytest` 只写结果、不生成 HTML；`conftest.pytest_sessionfinish → finalize_report_session → generate_report` 调 allure CLI 生成 HTML。`enable_allure_report` 控制是否生成（默认开），`auto_open_report` 控制是否 detached `allure open`（默认开）。`allure open` 子进程需脱离 pytest 进程树，否则随 pytest 退出被回收、页面打不开（某些会拆进程树的沙箱/CI 环境可能仍无法保活，真实终端正常）。
- **前置环境（打开报告必需）**：`generate_report` 在生成前检测 `allure` 是否可用（需 Java(JRE/JDK 8+) 且 `allure` 命令可运行）；任一缺失则如实返回非 0 并打印**跨平台安装指引**，绝不静默失败。
- **报告内含环境信息**：`generate_report` 在 `allure generate` 前写 `allure-results/environment.properties`（`Environment`/`BaseURL`/`Python`/`OS`/`Allure`/`GeneratedAt`，取自 `config.yaml` 与运行时）。**键名不能含空格**：Allure 按 Java Properties 解析，空格会被当作键值分隔符（如 `Test Environment=dev` 会被拆成 `Test` / `Environment=dev` 两列）。Allure **Environment** 控件展示该信息。

### 7) `pytest.ini` 的 bool 型开关不能有行内注释 ⚠️
- 现象：启动时报 `ValueError: invalid truth value 'true   # 是否 allure generate'`，整个会话（连 `--collect-only`）直接失败。
- 原因：`enable_allure_report`/`auto_open_report`/`enable_email_report` 注册为 `type="bool"`，pytest 的 `_strtobool` **把等号后整行（含 `#` 注释）当值解析**——ini 的 `#` 只在行首生效。
- 规避：注释单独成行写在开关**上方**；只写 `true`/`false`：

```ini
# 是否 allure generate（注释必须在上一行，不能写行内）
enable_allure_report = true
```

### 8) 断言类型别名漏分派 → 「HTTP 200 却断言失败」
- 现象：断言 `- status_code: { expected: 200 }` 在真实返回 200 时仍失败，错误信息为 `未知断言类型 'status_code'`。
- 原因：`assert_spec` 虽把 actual 置为 `resp.status_code`，但 `_check` 按 `atype` 分支时**没有 `status_code` 分支**，落到了「未知断言类型」兜底。
- 规避：`_check` 入口先做别名归一化（`status_code`/`status` → equals；`eq/ne/gt/lt/gte/lte/matches` → 对应全名），见第三节与第六节。生成后**必须跑一次只含 `status_code` 断言的用例**确认通过。

---

## 十二、Allure 前置环境（Java + allure-commandline）

打开/生成 Allure 报告依赖两个可执行件（Java + allure-commandline），**缺失时框架会给出安装指引而非静默失败**（`report_generator._allure_bin()` 在生成前用 `allure --version` 探测；也可设置环境变量 `ALLURE_BIN` 指向 allure 可执行文件）。

### 依赖与检测
- **Java(JRE/JDK 8+)**：`allure` 是 Java 程序，缺 Java 时 `allure --version` 会报 `java: command not found` 或运行异常。
- **allure-commandline CLI**：`allure` 需在 `PATH`（或 `ALLURE_BIN` 指向其可执行文件）。`report_generator` 用 `allure --version` 验证「能真正运行」（依赖 Java）；缺失则 `generate_report` 返回非 0 并打印下方安装指引，不静默失败、不阻断用例。

### 跨平台安装（任一即可）
- **Node 环境（最通用）**：`npm install -g allure-commandline`
- **Windows**：`scoop install allure` / `choco install allure-commandline` / `winget install qameta.allure`
- **macOS**：`brew install allure`（Java：`brew install openjdk`）
- **Linux**：`sudo apt install allure`（Java：`sudo apt install default-jre`）/ `snap install allure`
- **GitHub 发布包**：https://github.com/allure-framework/allure2/releases 下载 zip 解压并加入 `PATH`
- **回退**：设环境变量 `ALLURE_BIN` 直接指向 `allure` 可执行文件

安装后请重启终端使 `PATH` 生效。

---

## 十三、功能开关（pytest.ini）

所有功能开关集中在 `pytest.ini`，由 `conftest.py` 读取（环境变量优先覆盖，便于 CI 动态开关）：

| 开关 | 默认 | 作用 | 环境变量覆盖 |
|------|------|------|--------------|
| `enable_allure_report` | true | 是否 `allure generate` 生成 HTML | `ENABLE_ALLURE_REPORT` |
| `auto_open_report` | true | 生成后是否 detached `allure open` | `AUTO_OPEN_REPORT` |
| `enable_email_report` | false | 测试完成后是否发送邮件（需 `config.yaml` 的 `mail:` 节） | `ENABLE_EMAIL_REPORT` |

> ⚠️ **ini 写法**：以上开关为 `type="bool"`，值行内**禁止写 `#` 注释**（pytest 会把整行当值 → `ValueError: invalid truth value`）。
> 注释必须单独成行写在开关上方；写入前按第十一节-7 复核。

- **重试实现**：失败重试交由原生 `pytest-rerunfailures` 插件负责（`pytest.ini` 的 `addopts` 中 `--reruns N --reruns-delay S`，默认 `--reruns 1 --reruns-delay 1`），框架不自行实现重跑；`allure-pytest` 会按 `historyId` 自动在报告生成 **Retries 视图**（展示每次重跑 attempt 的状态/耗时/错误），控制台如实打印 `rerun` 过程。`report.py` 仍保留 `prune_reruns` 作为兜底（按 `historyId` 仅保留最终一次结果），`build_summary` 也按 `historyId` 去重，因此该 case 只体现最终状态（最终成功=`passed`，最终失败=`failed`），不增加用例计数、不保留重试中间态。
- **环境选择**：`--env dev/prod` 或环境变量 `TEST_ENV` 选择 `data/<env>.yaml`（优先级 `--env` > `TEST_ENV` > `config.yaml` 的 `env` > `dev`），CI 用 `scripts/run_tests.py --env <env>` 切换。
- **邮件通知**：`enable_email_report=true` + `config.yaml` 的 `mail:` 节（`smtp_host`/`smtp_user`/`sender`/`receivers`/`use_ssl`/`use_tls`/`subject_prefix`/`attach_report`；`smtp_password` 用环境变量 `MAIL_SMTP_PASSWORD` 注入）；缺配置或发送异常仅告警不阻断（`common/mailer.send_report_email` 返回 `False`）。
- **并行（可选）**：在 `pytest.ini` 的 `addopts` 追加 `-n auto`（依赖 pytest-xdist）即可开启；`--dist loadscope` 已固定在 `addopts`，保证同一 flow 的步骤不跨 worker。
- **报告生成与打开解耦**：`enable_allure_report=false` 时只写 allure 原始结果、不生成 HTML；`auto_open_report=false` 时生成但不打开。
