# -*- coding: utf-8 -*-
"""pytest 收集器：仅收集 flows/ 为用例（一个 flow = 一个 case）；apis/ 不直接收集。

被复用业务文件顶部加 component: true 跳过直接收集；pytest_plugins 在 conftest.py 注册。
"""
import logging
import os
import re
from pathlib import Path

import pytest

from common.config_reader import get_config
from common.request_client import ApiClient, ApiExecError
from common.context import ApiContext
from common.data_loader import load_case
from engine.executor import run_flow


def _find_apis_dir(start) -> Path:
    cur = Path(start) if isinstance(start, Path) else Path(start)
    if not cur.is_dir():
        cur = cur.parent
    for parent in [cur] + list(cur.parents):
        cand = parent / "testcases" / "apis"
        if cand.is_dir():
            return cand
    return Path("testcases") / "apis"


def _resolve_env(spec) -> str:
    """从 config.yaml 读 base_url；非空环境变量 BASE_URL 可覆盖；缺失即抛配置错误（不空跑）。"""
    cfg = get_config("config/config.yaml")
    base_url = cfg.get("base_url")
    env_val = os.environ.get("BASE_URL")
    if env_val is not None and str(env_val).strip() != "":
        return str(env_val).strip()
    if base_url is not None and str(base_url).strip() != "":
        return str(base_url).strip()
    raise RuntimeError(
        "config.yaml 未配置 base_url（或 BASE_URL 环境变量为空），无法运行；"
        "请先配置被测服务地址（禁止无服务空跑）。")


def pytest_collect_file(parent, file_path):
    p = Path(file_path)
    if p.suffix.lower() not in (".yaml", ".yml"):
        return None
    if "testcases" not in p.parts:
        return None
    if p.parent.name == "apis":          # 库目录不直接收集
        return None
    try:
        _case = load_case(p)
    except Exception:
        _case = {}
    if _case.get("component") or _case.get("reusable"):
        return None                       # 仅被 include 的业务，不独立收集
    # 跳过脚手架自带的未编辑骨架模板（含 <...> 占位符），避免被当作用例收集后运行失败
    try:
        raw = Path(file_path).read_text(encoding="utf-8")
    except Exception:
        raw = ""
    if re.search(r"<(http_method|resource|action|api_name|flow_title|expected_value|断言说明|field)>", raw):
        return None
    return YamlFile.from_parent(parent, path=p)


class YamlFile(pytest.File):
    def collect(self):
        case = load_case(self.path)
        title = case.get("title") or case.get("name") or self.path.stem
        spec = dict(case)
        spec["__title__"] = title
        # 一个 business flow = 一个 case：单个 ApiItem，steps 在 runtest 内顺序执行
        yield ApiItem.from_parent(self, name=title, spec=spec)


class ApiItem(pytest.Item):
    def __init__(self, name, parent, **kwargs):
        self.spec = kwargs.pop("spec")
        super().__init__(name=name, parent=parent, **kwargs)

    def runtest(self):
        base_url = _resolve_env(self.spec)
        token = get_config("config/config.yaml").get("token")
        client = ApiClient(base_url, token=token)
        ctx = ApiContext(biz_title=self.spec.get("__title__"),
                         base_dir=self.parent.path.parent,
                         apis_dir=_find_apis_dir(self.parent.path))
        run_flow(client, self.spec, ctx, log=logging.getLogger("engine.flow"))   # 一个 case 内顺序执行全部步骤

    def repr_failure(self, excinfo):
        # 只展示可读摘要（不附框架堆栈）；detail 已透传到 Allure 失败详情附件
        return str(excinfo.value)
