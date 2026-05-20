from pathlib import Path

from app_v4.desktop.theme.generate_qss import generate_qss


def test_generate_qss_maps_tokens(tmp_path):
    tokens = tmp_path / "tokens.css"
    tokens.write_text(":root { --ink: #0a0a0a; --amber: #ffb800; --bone: #fafaf7; }", encoding="utf-8")

    qss = generate_qss(tokens)

    assert "#0a0a0a" in qss
    assert "#ffb800" in qss
    assert "#fafaf7" in qss
