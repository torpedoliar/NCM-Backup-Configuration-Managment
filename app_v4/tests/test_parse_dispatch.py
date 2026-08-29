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
    # parse_config is total. The first three inputs stop at detect_dialect and
    # exercise only the unknown branch; the last two trip a marker and so are
    # actually handed to a delegate parser, which is the only place a raise is
    # plausible. (The API takes str, so "garbage" here means a str carrying
    # control codepoints, not bytes.)
    degenerate = [
        "",
        "\n\n",
        "\x00\xff\x1b[2J garbage \x7f",
        "interface port1.0.",
        "@ 1\t1.3.6.1.2.1.17.7.1.4.3.1\n2\t.2.7\t 4\t 99999999\tzz\n",
    ]
    for text in degenerate:
        cfg = parse_config(text)
        assert cfg.ports == []
        assert cfg.warnings


def test_recognised_dialect_with_no_ports_is_warned():
    # A Dell config whose description quotes a neighbour's AWP port name trips
    # the awplus marker first and is routed to the wrong parser: awplus.parse
    # finds nothing and, having read no malformed rows, warns about nothing.
    # Without the dispatcher's own check this is indistinguishable from a switch
    # that genuinely has no ports.
    text = (
        "interface ethernet g1\n"
        'description "uplink to interface port1.0.24 on core"\n'
    )
    assert detect_dialect(text) == "awplus"  # the misroute, pinned
    cfg = parse_config(text)
    assert cfg.ports == []
    assert any("parsed no ports" in w for w in cfg.warnings)


def test_ports_found_adds_no_dispatcher_warning():
    # Control for the test above: the warning is caused by the empty result, not
    # attached to every dispatched parse.
    cfg = parse_config((FX / "dell.txt").read_text(encoding="utf-8"))
    assert cfg.ports
    assert not any("parsed no ports" in w for w in cfg.warnings)


def test_detect_model_heuristic():
    from app_v4.net.model_detect import detect_model

    assert detect_model("hostname sw1\nAT-GS950/24PS config\n", "awplus") == "AT-GS950/24PS"
    assert detect_model("Dell Networking N1548P\n", "dell") == "N1548P"
    assert detect_model("hostname x\n", "awplus") is None
