from pathlib import Path

from app_v4.net.config_parsers import awplus

FIXTURE = Path(__file__).parent / "fixtures" / "network_doc" / "awplus.txt"


def _port(cfg, name):
    return next(p for p in cfg.ports if p.name == name)


def test_awplus_hostname_and_vlan_names():
    cfg = awplus.parse(FIXTURE.read_text(encoding="utf-8"))
    assert cfg.hostname == "Office2"
    names = {v.id: v.name for v in cfg.vlans}
    assert names[4] == "BOD"
    assert names[88] == "IPH-DEVICE"


def test_awplus_trunk_port_native_and_allowed():
    cfg = awplus.parse(FIXTURE.read_text(encoding="utf-8"))
    p = _port(cfg, "port1.0.1")
    assert p.mode == "trunk"
    assert p.native_vlan == 11
    assert p.trunk_allowed_vlans == [88]
    assert p.enabled is False  # has 'shutdown'


def test_awplus_access_port_and_range_expansion():
    cfg = awplus.parse(FIXTURE.read_text(encoding="utf-8"))
    p6 = _port(cfg, "port1.0.6")
    assert p6.mode == "access"
    assert p6.access_vlan == 11
    p8 = _port(cfg, "port1.0.8")
    assert p8.trunk_allowed_vlans == [4, 5, 9, 14, 15, 18, 20, 24, 25, 27]


def test_awplus_clean_fixture_produces_no_warnings():
    cfg = awplus.parse(FIXTURE.read_text(encoding="utf-8"))
    assert cfg.warnings == []


def test_awplus_multiple_trunk_vlan_add_lines_accumulate():
    """Two switchport trunk allowed vlan add lines on the same port accumulate
    with deduplication and deterministic ascending order."""
    cfg = awplus.parse(
        "hostname X\n"
        "!\n"
        "interface port1.0.1\n"
        " switchport mode trunk\n"
        " switchport trunk allowed vlan add 10,20\n"
        " switchport trunk allowed vlan add 20,30\n"
        "!\n"
    )
    p = _port(cfg, "port1.0.1")
    assert p.trunk_allowed_vlans == [10, 20, 30]


def test_awplus_multiple_trunk_vlan_add_lines_with_range():
    """Range expansion + duplicate across multiple add lines."""
    cfg = awplus.parse(
        "hostname X\n"
        "!\n"
        "interface port1.0.1\n"
        " switchport mode trunk\n"
        " switchport trunk allowed vlan add 88\n"
        " switchport trunk allowed vlan add 4-6,88\n"
        "!\n"
    )
    p = _port(cfg, "port1.0.1")
    assert p.trunk_allowed_vlans == [88, 4, 5, 6]


def test_awplus_malformed_vlan_id_warns_instead_of_raising():
    cfg = awplus.parse(
        "hostname X\n"
        "!\n"
        "interface port1.0.1\n"
        " switchport mode access\n"
        " switchport access vlan abc\n"
        " switchport trunk native vlan xx\n"
        "!\n"
    )
    assert cfg.hostname == "X"
    p = _port(cfg, "port1.0.1")
    assert p.access_vlan is None
    assert p.native_vlan is None
    assert len(cfg.warnings) == 2
    assert all("unparsable vlan id" in w for w in cfg.warnings)
