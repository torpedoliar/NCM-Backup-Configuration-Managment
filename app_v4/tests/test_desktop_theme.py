from __future__ import annotations

from app_v4.desktop.theme import load_theme_qss


def test_load_theme_qss_returns_full_stylesheet():
    qss = load_theme_qss()

    assert "QWidget" in qss
    assert "background:" in qss
    assert "color:" in qss
    assert len(qss) > 100
