# -*- coding: utf-8 -*-
"""执行引擎：一个 business flow = 一个 case；steps 顺序执行，每 API 包为 allure step。
失败保留证据（artifacts/ + Allure 挂载），业务内任一失败即硬停止后续步骤。
依赖方向：engine -> common -> utils；本模块不 import 具体接口名。
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import allure
from requests.exceptions import RequestException

from common.paths import ARTIFACTS_DIR
from common.context import ApiContext
from common.request_client import ApiClient, ApiExecError
from common.data_loader import load_case
from utils.dicts import deep_merge
from utils.templating import resolve
from utils.extract import jsonpath_extract, parse_extract
from utils.redact import redact


def normalize_method(method) -> str:
    return str(method or "").strip().upper() or "GET"


def _find_apis_dir(start: Path) -> Path:
    """从某文件向上找含 apis/ 的 testcases 目录。"""
    cur = start if start.is_dir() else start.parent
    for parent in [cur] + list(cur.parents):
        cand = parent / "testcases" / "apis"
        if cand.is_dir():
            return cand
    return Path("testcases") / "apis"


def _resolve_api_path(include: str, base_dir: Path, apis_dir: Path) -> Path:
    """解析 include 路径：业务目录 apis/flows -> 全局 testcases/apis/flows -> 业务文件相对。"""
    inc = Path(include)
    candidates = [
        base_dir / inc,
        apis_dir.parent / inc,           # testcases/ + include
        Path("testcases") / inc,
        base_dir / "testcases" / inc,
    ]
    for c in candidates:
        if c.is_file():
            return c
    return base_dir / inc


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
    """由 step 构建单次 API 调用的 spec；with 覆盖 request 及 validate/extract/extract_global。"""
    if isinstance(step, str):
        step = {"include": step}
    path = _resolve_api_path(step["include"], base_dir, apis_dir)
    api = load_case(path)                        # 单 API 定义（嵌套 flow 由 collector 递归展开）
    spec = dict(api)
    if "name" in step:
        spec["name"] = step["name"]
    if "with" in step:
        w = step["with"]
        # with 兼容「顶层直平铺」与「with.request 嵌套」两种写法，request 部分深度合并
        overlay_request = w.get("request") if isinstance(w.get("request"), dict) else w
        spec["request"] = deep_merge(api.get("request", {}), overlay_request)
        for k in ("validate", "extract", "extract_global"):
            if k in w:
                spec[k] = w[k]
    return spec


def _save_evidence(api_name, *, request=None, response=None, error=None, detail=None):
    """失败现场留证：请求/响应快照写入 artifacts/ 并挂载 Allure（含可读文本）。"""
    import json as _json, time as _t
    from engine.reporting.report import attach_failure_artifact, attach_failure_text
    art_dir = ARTIFACTS_DIR
    art_dir.mkdir(parents=True, exist_ok=True)
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
    # 传 ctx（而非 ctx.data）：resolve 走 ApiContext.runtime()，可见 extract + extract_global 全局变量
    method = normalize_method(resolve(req.get("method"), ctx))   # 解析 + 规范化（method 经 data/ 常量解析）
    target = resolve(req.get("url") or req.get("path") or "", ctx)
    headers = resolve(req.get("headers", {}), ctx)
    params = resolve(req.get("params") or req.get("query") or {}, ctx)
    json_body = resolve(req.get("json"), ctx) or None                                          # application/json
    form_body = resolve(req.get("form") or req.get("data"), ctx) or None                       # x-www-form-urlencoded
    files_body = resolve(req.get("files"), ctx) or None                                        # multipart/form-data
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
        for key, val in (api_spec.get("extract") or {}).items():
            _mode, jp, default = parse_extract(val)
            ctx.set(key, jsonpath_extract(resp.json, jp, default))
        for key, val in (api_spec.get("extract_global") or {}).items():
            _mode, jp, default = parse_extract(val)
            ctx.set_global(key, jsonpath_extract(resp.json, jp, default))
        try:
            from common.assert_utils import assert_spec
            assert_spec(resp, api_spec.get("validate") or [], ctx,
                        api_name=api_name, biz_title=ctx.biz_title)
        except AssertionError as e:
            detail = _format_failure(api_name, client, method, target, headers,
                                     params, body_payload, resp, str(e))
            _save_evidence(api_name, response={"status": resp.status_code,
                                              "elapsed_ms": resp.elapsed_ms,
                                              "headers": redact(dict(resp.headers)),
                                              "json": redact(resp.json), "text": resp.text[:2000]},
                          error=str(e), detail=detail)
            setattr(e, "details", detail)   # 透传到 run_flow 的 ERROR 日志与 Allure 失败详情附件
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
        method = normalize_method(resolve(req.get("method"), ctx))
        target = resolve(req.get("url") or req.get("path") or "", ctx)
        api_name = spec.get("name", target)
        if log:
            log.info("步骤 %d/%d · %s %s [%s]", i, total, method, target, api_name)   # 日志含步骤
        try:
            _run_single_api(client, spec, ctx)       # 内部 allure.step + 软断言 + 失败留证
        except (AssertionError, ApiExecError) as e:
            if log:
                detail = getattr(e, "details", None) or str(e)
                log.error("步骤 %d/%d 失败，硬停止后续步骤 [%s]\n%s", i, total, api_name, detail)
                for j in range(i + 1, total + 1):
                    rs = steps[j - 1]
                    rreq = rs.get("request", {}) or {}
                    rname = rs.get("name") or resolve(rreq.get("url") or rreq.get("path") or "", ctx)
                    log.warning("⏭️  API「%s」已跳过：上游 API『%s』执行失败，已停止执行本业务后续 API",
                                rname, api_name)
            raise                                     # 任一步骤失败 -> 本 case 失败，后续步骤不再执行
        if log:
            log.info("步骤 %d/%d 通过 [%s]", i, total, api_name)
