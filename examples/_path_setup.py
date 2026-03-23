#!/usr/bin/env python3
"""为 examples 目录脚本注入 src 路径。"""

import os
import sys


def ensure_src_path():
    src_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "src",
    )
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
