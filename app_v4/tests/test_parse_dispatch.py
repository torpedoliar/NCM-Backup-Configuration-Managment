from pathlib import Path

from app_v4.net.config_parsers import detect_dialect, parse_config

FX = Path(__file__).parent / "fixtures" / "network_doc"


def test_detect_dialect():
    assert detect_dialect((FX / "awplus.txt").read_text(encoding="utf-8")) == "awplus"
    assert detect_dialect((FX / "dell.txt").read_text(encoding="utf-8")) == "dell"
    assert detect_dialect((FX / "websmart.txt").read_text(encoding="utf-8")) == "websmart"
    assert detect_dialect((FX / "websmart_v2.txt").read_text(encoding="utf-8")) == "websmart"


def test_parse_config_routes_each_dialect():
    for name in ("awplus", "dell", "websmart", "websmart_v2"):
        cfg = parse_config((FX / f"{name}.txt").read_text(encoding="utf-8"))
        assert cfg.ports, f"{name} produced no ports"


def test_parse_config_unknown_is_warning_not_error():
    cfg = parse_config("this is not a switch config at all\n")
    assert cfg.ports == []
    assert cfg.warnings


def test_parse_config_never_raises_on_degenerate_input():
    # parse_config is total: empty, whitespace and binary garbage must all come
    # back as an empty ParsedConfig carrying a warning, never as an exception.
    for text in ("", "\n\n", "\x00\xff\x1b[2J garbage \x7f"):
        cfg = parse_config(text)
        assert cfg.ports == []
        assert cfg.warnings
