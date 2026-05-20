from __future__ import annotations

import re
from pathlib import Path


def _tokens(tokens_path: Path) -> dict[str, str]:
    text = tokens_path.read_text(encoding="utf-8")
    return {name: value.strip() for name, value in re.findall(r"--([a-z0-9-]+):\s*([^;]+);", text)}


def generate_qss(tokens_path: Path) -> str:
    t = _tokens(tokens_path)
    return f"""
QWidget {{ background: {t['ink']}; color: {t['bone']}; font-family: Geist; }}
QFrame#Sidebar {{ background: {t['ink']}; border-right: 1px solid {t['line']}; }}
QFrame#Topbar {{ background: {t['ink']}; border-bottom: 1px dashed {t['amber']}; }}
QLabel#Brand {{ color: {t['bone']}; font-family: JetBrains Mono; font-size: 28px; font-weight: 800; }}
QLabel#Marker {{ color: {t['muted']}; font-family: JetBrains Mono; letter-spacing: 2px; }}
QLabel#ServicePulse {{ color: {t['green']}; border: 1px solid {t['green']}; padding: 6px 10px; }}
QPushButton {{ background: {t['surface']}; color: {t['bone']}; border: 1px solid {t['line']}; border-radius: 0; padding: 9px; text-align: left; }}
QPushButton:hover {{ border-color: {t['amber']}; color: {t['amber']}; }}
QPushButton[active="true"] {{ border-left: 3px solid {t['amber']}; color: {t['bone']}; }}
""".strip()
