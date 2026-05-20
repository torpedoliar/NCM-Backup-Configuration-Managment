from __future__ import annotations

import re
from pathlib import Path


def generate_qss(tokens_path: Path) -> str:
    text = tokens_path.read_text(encoding="utf-8")
    tokens = dict(re.findall(r"--([a-z0-9-]+):\s*([^;]+);", text))
    return f"""
QWidget {{ background: {tokens['ink'].strip()}; color: {tokens['bone'].strip()}; }}
QLabel#Brand {{ color: {tokens['amber'].strip()}; }}
QPushButton:hover {{ border-color: {tokens['amber'].strip()}; }}
""".strip()
