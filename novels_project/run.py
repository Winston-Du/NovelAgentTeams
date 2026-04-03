#!/usr/bin/env python
"""
主运行脚本 - 委托给新的 CLI 入口点

向后兼容: python run.py 等价于 novels 命令
"""
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from novels_project.cli import main

if __name__ == "__main__":
    main()
