# -*- coding: utf-8 -*-
"""零代码 API 框架脚手架：把 templates/ 复制到目标目录并注入必要配置。

由 api-zero-code-framework skill 调用；仅用标准库，不依赖三方包。
用法：
    python scaffold.py --root ./myapi --base-url https://api.example.com --env dev
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

# 兼容 Windows 等非 UTF-8 控制台：避免打印中文时 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"


def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def _inject_config(root: Path, base_url: str, env: str) -> None:
    cfg = root / "config" / "config.yaml"
    if not cfg.is_file():
        return
    text = cfg.read_text(encoding="utf-8")
    if base_url:
        text = re.sub(r'(?m)^base_url:.*$', f'base_url: "{base_url}"', text)
    text = re.sub(r'(?m)^env:.*$', f'env: {env}', text)
    cfg.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="生成零代码 API 自动化框架")
    ap.add_argument("--root", default=".", help="目标根目录（默认当前目录）")
    ap.add_argument("--base-url", default="", help="被测服务 base_url（运行必需）")
    ap.add_argument("--env", default="test", help="默认环境 dev/test/staging/prod")
    args = ap.parse_args()

    if not TEMPLATES.is_dir():
        raise SystemExit(f"[scaffold] templates 目录缺失：{TEMPLATES}")

    root = Path(args.root).resolve()
    # 重跑脚手架时，未显式传入 --base-url 则保留已有 base_url（避免清空已配置地址）
    prev_base_url = ""
    prev_cfg = root / "config" / "config.yaml"
    if prev_cfg.is_file():
        m = re.search(r'(?m)^base_url:\s*(.*)$', prev_cfg.read_text(encoding="utf-8"))
        if m:
            v = m.group(1).split('#', 1)[0].strip().strip('"').strip("'")
            if v:
                prev_base_url = v
    _copy_tree(TEMPLATES, root)
    base_url = args.base_url or prev_base_url
    _inject_config(root, base_url, args.env)

    print(f"[scaffold] 框架已生成到：{root}")
    if not base_url:
        print("[scaffold] ⚠️  未提供 --base-url 且无历史配置，请在 config/config.yaml 填写 base_url，否则运行会报错")
    print(f"[scaffold] 下一步：在 testcases/apis 与 testcases/flows 编写 YAML 用例（无需改 Python）")
    print(f"[scaffold] 运行：python scripts/run_tests.py --env {args.env}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
