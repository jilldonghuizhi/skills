# -*- coding: utf-8 -*-
"""多类型断言引擎：validate 列表 -> 逐条执行 -> 软断言汇总失败。

支持 equals/ne/gt/lt/gte/lte/contains/not_contains/in/not_in/length/min_length/
max_length/type/regex/exists/not_exists/schema/status_code(status)，含别名分派。
错误信息格式见 reference_contract.md 第三节；期望与实值均带类型（如 '200' (str)）。
"""
from typing import Any, Dict, List, Optional, Tuple

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore

from utils.templating import resolve


class ApiExecError(Exception):
    """请求级失败，触发业务链路硬停止。"""


_STATUS_ALIASES = ("status_code", "status")  # 状态码断言：actual 隐含为 resp.status_code

_ALIAS = {
    "eq": "equals",
    "ne": "not_equals",
    "gt": "greater_than",
    "lt": "less_than",
    "gte": "greater_or_equal",
    "lte": "less_or_equal",
    "matches": "regex",
}

_TYPE_MAP = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "none": type(None),
    "null": type(None),
}


def assert_spec(resp, validate, ctx, *, api_name="", biz_title="") -> None:
    """执行 validate 列表；任一失败汇总后抛 AssertionError（API 内软断言）。"""
    specs = _normalize_validate(validate)
    failures = []
    for atype, raw in specs:
        spec = dict(raw) if isinstance(raw, dict) else {}
        # expected/pattern 支持 ${...} 常量（如 expected: "${expect.success_code}"）
        for key in ("expected", "pattern"):
            if key in spec:
                spec[key] = resolve(spec[key], ctx)
        # status_code/status 无 actual 时，actual 隐含为响应状态码（勿走 _resolve_actual）
        if str(atype).strip().lower() in _STATUS_ALIASES and "actual" not in spec:
            actual, src = resp.status_code, "响应状态码"
        else:
            actual, src = _resolve_actual(spec.get("actual"), resp, ctx)
        try:
            _check(atype, actual, spec, resp, ctx)
        except AssertionError as e:
            failures.append((atype, spec.get("name", atype), str(e), src))
    if failures:
        raise AssertionError(_format_summary(biz_title, api_name, failures))


def _normalize_validate(validate) -> List[Tuple[str, Any]]:
    if validate is None:
        return []
    if isinstance(validate, dict):
        return [(k, v) for k, v in validate.items()]
    if isinstance(validate, list):
        out = []
        for item in validate:
            if isinstance(item, dict):
                out.extend(item.items())
            else:
                out.append(("equals", item))
        return out
    return [("equals", validate)]


def _resolve_actual(expr, resp, ctx):
    """返回 (值, 取值说明)。actual 支持 status_code / $.x / ${var} / 字面量。"""
    if expr is None:
        return None, "无 actual"
    s = str(expr).strip()
    if s == "status_code":
        return resp.status_code, "响应状态码"
    if s.startswith("$."):
        data = resp.json if resp.json is not None else None
        if data is None:
            raise AssertionError(
                f"响应非 JSON（HTTP {resp.status_code}，可能路径或方法不符），无法按 JSONPath 取值 {s}")
        from utils.extract import jsonpath_extract
        return jsonpath_extract(data, s, None), f"响应 {s}"
    if s.startswith("${"):
        return resolve(s, ctx), f"变量 {s}"
    return s, f"字面量 {s}"


def _fmt(v) -> str:
    return f"{v!r} ({type(v).__name__})"


def _fail(msg: str):
    raise AssertionError(msg)


def _check(atype, actual, spec, resp=None, ctx=None) -> None:
    at = str(atype).strip().lower()
    expected = spec.get("expected")
    # ① status_code / status -> equals（actual 已由 assert_spec 置为 resp.status_code）
    if at in _STATUS_ALIASES:
        at = "equals"
    # ② 其余别名归一化：eq/ne/gt/lt/gte/lte/matches
    at = _ALIAS.get(at, at)

    if at == "equals":
        if _num_eq(actual, expected):
            return
        _fail(f"期望 == {_fmt(expected)} | 实际 {_fmt(actual)}")
    elif at == "not_equals":
        if not _num_eq(actual, expected):
            return
        _fail(f"期望 != {_fmt(expected)} | 实际 {_fmt(actual)}")
    elif at == "greater_than":
        if _to_num(actual) > _to_num(expected):
            return
        _fail(f"期望 > {_fmt(expected)} | 实际 {_fmt(actual)}")
    elif at == "less_than":
        if _to_num(actual) < _to_num(expected):
            return
        _fail(f"期望 < {_fmt(expected)} | 实际 {_fmt(actual)}")
    elif at == "greater_or_equal":
        if _to_num(actual) >= _to_num(expected):
            return
        _fail(f"期望 >= {_fmt(expected)} | 实际 {_fmt(actual)}")
    elif at == "less_or_equal":
        if _to_num(actual) <= _to_num(expected):
            return
        _fail(f"期望 <= {_fmt(expected)} | 实际 {_fmt(actual)}")
    elif at == "contains":
        if _contains(actual, expected):
            return
        _fail(f"期望包含 {_fmt(expected)} | 实际 {_fmt(actual)}")
    elif at == "not_contains":
        if not _contains(actual, expected):
            return
        _fail(f"期望不包含 {_fmt(expected)} | 实际 {_fmt(actual)}")
    elif at == "in":
        if actual in (expected or []):
            return
        _fail(f"期望属于集合 {_fmt(expected)} | 实际 {_fmt(actual)}")
    elif at == "not_in":
        if actual not in (expected or []):
            return
        _fail(f"期望不属于集合 {_fmt(expected)} | 实际 {_fmt(actual)}")
    elif at == "length":
        if len(actual) == _to_num(expected):
            return
        _fail(f"期望长度 == {_fmt(expected)} | 实际长度 {len(actual)}")
    elif at == "min_length":
        if len(actual) >= _to_num(expected):
            return
        _fail(f"期望长度 >= {_fmt(expected)} | 实际长度 {len(actual)}")
    elif at == "max_length":
        if len(actual) <= _to_num(expected):
            return
        _fail(f"期望长度 <= {_fmt(expected)} | 实际长度 {len(actual)}")
    elif at == "type":
        tgt = _TYPE_MAP.get(str(expected).lower())
        if tgt is None:
            _fail(f"未知类型期望 {expected!r}")
        if isinstance(actual, tgt):
            return
        _fail(f"期望类型 {expected} | 实际类型 {type(actual).__name__}")
    elif at == "regex":
        import re
        pat = str(spec.get("pattern", expected))
        if re.search(pat, str(actual)) is not None:
            return
        _fail(f"期望匹配正则 {pat!r} | 实际 {_fmt(actual)}")
    elif at == "exists":
        if actual is not None and actual != "":
            return
        _fail(f"期望存在且非空 | 实际 {_fmt(actual)}")
    elif at == "not_exists":
        if actual is None or actual == "":
            return
        _fail(f"期望不存在或为空 | 实际 {_fmt(actual)}")
    elif at == "schema":
        if jsonschema is None:
            _fail("jsonschema 未安装，无法执行 schema 断言（请 pip install jsonschema）")
        try:
            jsonschema.validate(instance=actual, schema=expected)
            return
        except jsonschema.ValidationError as e:
            _fail(f"schema 校验失败: {e.message}")
    else:
        _fail(f"未知断言类型 {atype!r}")


def _num_eq(a, b) -> bool:
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return a == b


def _to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _contains(actual, expected) -> bool:
    try:
        return expected in actual
    except TypeError:
        return False


def _format_summary(biz_title: str, api_name: str, failures) -> str:
    """按第三节格式汇总断言失败：业务/接口标题 + 编号列表（类型·名称·期望|实际·取值路径）。"""
    lines = [f"❌ 业务「{biz_title}」· API「{api_name}」断言失败：共 {len(failures)} 项未通过"]
    for i, (atype, name, err, src) in enumerate(failures, 1):
        lines.append(f"  {i}. [{atype} · {name}] {err}  （取值: {src}）")
    return "\n".join(lines)
