#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Explorer 取证瘦身：裁剪 Playwright MCP 可见文本，控制单次取证 Token。

只做纯文本处理（折叠空行、去除重复行、按预算截断、完整原文落盘），
不解析 DOM / 选择器 / 元素属性 —— 与 Explorer「只观察、不获取 DOM」边界一致。

用法:
    python trim_visible_text.py --file raw.txt --budget 1500
    python trim_visible_text.py --file raw.txt --dump spec/evidence/p1.txt
    type raw.txt | python trim_visible_text.py --budget 800
"""
import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def build_counter(encoding="cl100k_base"):
    """优先 tiktoken，缺失时回退启发式估算。"""
    try:
        import tiktoken
        enc = tiktoken.get_encoding(encoding)
        return lambda t: len(enc.encode(t)), f"tiktoken:{encoding}"
    except Exception:
        def heuristic(t):
            zh = len(re.findall(r"[\u4e00-\u9fff]", t))
            return int(zh * 1.2 + (len(t) - zh) / 3.5) + 1
        return heuristic, "heuristic(zh*1.2+other/3.5)"


def collapse_blank(lines):
    out, blank = [], False
    for ln in lines:
        cur = ln.strip() == ""
        if cur and blank:
            continue
        out.append(ln)
        blank = cur
    return out


def dedupe_repeated(lines, min_repeat=3):
    """去除重复出现的导航/页脚式行：出现次数 >= min_repeat 的相同行只保留首次。"""
    counts = {}
    for ln in lines:
        key = ln.strip()
        if key:
            counts[key] = counts.get(key, 0) + 1
    seen, out = set(), []
    for ln in lines:
        key = ln.strip()
        if key and counts.get(key, 0) >= min_repeat:
            if key in seen:
                continue
            seen.add(key)
        out.append(ln)
    return out


def hard_trim(text, budget, counter):
    """兜底：head 部分本身已超预算时（超长列表页），按预算比例硬截断。"""
    note = "\n[...已按Token预算硬截断，完整原文见落盘文件...]"
    if counter(text + note) <= budget:
        return text + note
    ratio = budget / max(counter(text + note), 1)
    lo, hi = 1, max(1, int(len(text) * ratio * 1.1))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if counter(text[:mid] + note) <= budget:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + note


def trim_by_budget(text, budget, counter, keep_head_ratio=0.6):
    """按 Token 预算保留 head + tail，中间折叠为省略提示。"""
    if counter(text) <= budget:
        return text, 0
    lines = text.splitlines()
    head_n = max(1, int(len(lines) * keep_head_ratio))
    head, tail = lines[:head_n], lines[head_n:]
    note = "\n[...中间内容已按Token预算折叠，完整原文见落盘文件...]\n"
    # 二分求最大可保留的 tail 行数
    lo, hi, best = 0, len(tail), 0
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = "\n".join(head) + note + "\n".join(tail[-mid:]) if mid else "\n".join(head) + note
        if counter(candidate) <= budget:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    kept = "\n".join(head) + note + ("\n".join(tail[-best:]) if best else "")
    kept = "\n".join(collapse_blank(kept.splitlines()))
    if counter(kept) > budget:
        kept = hard_trim(kept, budget, counter)
    return kept, counter(text) - counter(kept)


def main():
    parser = argparse.ArgumentParser(description="裁剪可见文本以控制取证 Token")
    parser.add_argument("--file", help="原始可见文本文件；缺省读 stdin")
    parser.add_argument("--budget", type=int, default=1500, help="单次取证 Token 预算，默认 1500")
    parser.add_argument("--dump", help="完整原文落盘路径（REC 中只引用路径）")
    parser.add_argument("--no-dedupe", action="store_true", help="保留重复行（默认去除重复导航行）")
    parser.add_argument("--encoding", default="cl100k_base")
    args = parser.parse_args()

    raw = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    if not raw.strip():
        print("输入为空", file=sys.stderr)
        return 1

    counter, mode = build_counter(args.encoding)
    before = counter(raw)

    if args.dump:
        dump_path = Path(args.dump)
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(raw, encoding="utf-8")

    lines = collapse_blank(raw.splitlines())
    if not args.no_dedupe:
        lines = dedupe_repeated(lines)
    cleaned = "\n".join(lines)

    trimmed, saved = trim_by_budget(cleaned, args.budget, counter)
    after = counter(trimmed)

    print(trimmed)
    print(
        f"\n[取证瘦身] 口径={mode} | 原始 {before} Token -> 裁剪后 {after} Token "
        f"(节省 {round((1 - after / before) * 100, 1)}%)"
        + (f" | 完整原文已落盘: {args.dump}" if args.dump else " | 未落盘（建议 --dump 后 REC 只引用路径）"),
        file=sys.stderr,
    )
    if after > args.budget:
        print(f"[取证瘦身] 警告：仍超预算 {args.budget} Token，请缩小取证区块或下调预算", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
