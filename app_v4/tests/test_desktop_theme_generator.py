from pathlib import Path

from app_v4.desktop.theme.generate_qss import generate_qss


def test_generate_qss_maps_ops_terminal_tokens(tmp_path):
    tokens = tmp_path / "tokens.css"
    tokens.write_text(
        ":root { --ink: #0a0a0a; --surface: #141414; --line: #262626; --amber: #ffb800; --bone: #fafaf7; --muted: #737373; --green: #4ade80; --red: #ff3838; }",
        encoding="utf-8",
    )

    qss = generate_qss(tokens)

    assert "QFrame#Sidebar" in qss
    assert "#0a0a0a" in qss
    assert "#ffb800" in qss
    assert "#4ade80" in qss
