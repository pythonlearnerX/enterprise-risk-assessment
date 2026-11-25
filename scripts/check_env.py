# -*- coding: utf-8 -*-
"""环境自检脚本：输出解释器、虚拟环境与关键版本，供「环境准备」环节截图。

用法（在项目根目录、已激活 .venv 的情况下）：
    python scripts/check_env.py
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parents[1]
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)

    print("=" * 56)
    print("risk_project_xuerui 环境自检")
    print("=" * 56)
    print(f"项目根目录 : {root}")
    print(f"Python     : {sys.version.split()[0]}")
    print(f"解释器路径 : {sys.executable}")
    print(f"基础解释器 : {getattr(sys, 'base_prefix', '(未知)')}")
    print(f"虚拟环境   : {'是' if in_venv else '否（请先激活 .venv）'}")
    print(f"venv 目录  : {sys.prefix}")
    print(f"系统平台   : {platform.platform()}")
    print(f"工作目录   : {Path.cwd()}")
    print("-" * 56)

    try:
        import pip  # noqa: F401

        print("pip        : 可用")
    except ImportError:
        print("pip        : 不可用")

    if not in_venv:
        print("提示：当前不在 .venv 中运行，请先激活虚拟环境。")
    print("=" * 56)


if __name__ == "__main__":
    main()
