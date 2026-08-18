from pathlib import Path

from app_v4.net.config_parsers import websmart_snmp

FIXTURE = Path(__file__).parent / "fixtures" / "network_doc" / "websmart.txt"
FIXTURE_V2 = Path(__file__).parent / "fixtures" / "network_doc" / "websmart_v2.txt"

_VLAN_STATIC = "1.3.6.1.2.1.17.7.1.4.3.1"
_PORT_VLAN = "1.3.6.1.2.1.17.7.1.4.5.1"


def _port(cfg, name):
    return next(p for p in cfg.ports if p.name == name)


def _dump(*lines: str) -> str:
    """Build a synthetic dump; each arg is already tab-separated."""
    return "\n".join(lines) + "\n"


def test_websmart_vlan_names():
    cfg = websmart_snmp.parse(FIXTURE.read_text(encoding="utf-8"))
    names = {v.id: v.name for v in cfg.vlans}
    assert names[1] == "DefaultVLAN"
    assert names[88] == "IPH-DEVICE"
    assert names[23] == "VIDCON-DEVICE"


def test_websmart_hostname():
    cfg = websmart_snmp.parse(FIXTURE.read_text(encoding="utf-8"))
    assert cfg.hostname == "ICT Network SW"


def test_websmart_egress_bitmap_decode():
    cfg = websmart_snmp.parse(FIXTURE.read_text(encoding="utf-8"))
    # vlan 88 egress ffffffffffff0000 -> ports 1..48 all members (trunk allowed)
    trunk_ports_on_88 = [p.name for p in cfg.ports if 88 in p.trunk_allowed_vlans]
    assert len(trunk_ports_on_88) >= 40
    # vlan 23 egress 0000000040010000 -> ports 34, 48
    members_23 = {int(p.name) for p in cfg.ports if 23 in p.trunk_allowed_vlans}
    assert {34, 48} == members_23


def test_websmart_pvid_gives_native_or_access():
    cfg = websmart_snmp.parse(FIXTURE.read_text(encoding="utf-8"))
    # port 1 PVID=6, port 8 PVID=205 (from dot1qPvid table)
    p1 = _port(cfg, "1")
    assert (p1.native_vlan == 6) or (p1.access_vlan == 6)
    p8 = _port(cfg, "8")
    assert (p8.native_vlan == 205) or (p8.access_vlan == 205)


def test_websmart_clean_fixture_has_no_warnings():
    cfg = websmart_snmp.parse(FIXTURE.read_text(encoding="utf-8"))
    assert cfg.warnings == []


def test_websmart_v2_parses_without_error():
    cfg = websmart_snmp.parse(FIXTURE_V2.read_text(encoding="utf-8"))
    assert cfg.ports  # some ports discovered
    assert isinstance(cfg.warnings, list)
    assert cfg.hostname == "Nutanix Switch"
    assert {v.id: v.name for v in cfg.vlans}[900] == "DMZ"


def test_crlf_input_parses_identically():
    # The dump is stored with CRLF endings. A caller that reads it without
    # newline translation must get the same result: the trailing CR is dropped
    # by slicing each octet string to its declared length.
    translated = websmart_snmp.parse(FIXTURE.read_text(encoding="utf-8"))
    literal = websmart_snmp.parse(FIXTURE.read_text(encoding="utf-8", newline=""))
    assert literal == translated
    assert literal.warnings == []


def test_port_without_membership_keeps_pvid_but_mode_unknown():
    # Port 49 has a PVID but appears in no VLAN egress bitmap, so there is no
    # evidence for trunk or access.
    cfg = websmart_snmp.parse(FIXTURE.read_text(encoding="utf-8"))
    p49 = _port(cfg, "49")
    assert p49.mode == "unknown"
    assert p49.access_vlan == 1
    assert p49.trunk_allowed_vlans == []


def test_bare_at_line_clears_base_oid():
    text = _dump(
        f"@   1\t{_PORT_VLAN}",
        "2\t.1.1\t66\t9",
        "@   2",
        "2\t.1.2\t66\t9",
    )
    cfg = websmart_snmp.parse(text)
    assert [p.name for p in cfg.ports] == ["1"]


def test_malformed_pvid_warns_and_keeps_other_ports():
    text = _dump(
        f"@   1\t{_PORT_VLAN}",
        "2\t.1.1\t66\t6",
        "2\t.1.2\t66\tnotanint",
    )
    cfg = websmart_snmp.parse(text)
    assert _port(cfg, "1").access_vlan == 6
    assert any("notanint" in w for w in cfg.warnings)


def test_malformed_oid_index_warns_and_does_not_raise():
    text = _dump(
        f"@   1\t{_VLAN_STATIC}",
        "2\t.1.xx\t 4\t   4\tTEST",
        "2\t.1.7\t 4\t   5\tVLAN7",
    )
    cfg = websmart_snmp.parse(text)
    assert [(v.id, v.name) for v in cfg.vlans] == [(7, "VLAN7")]
    assert any("xx" in w for w in cfg.warnings)


def test_malformed_declared_length_warns_and_does_not_raise():
    text = _dump(
        f"@   1\t{_VLAN_STATIC}",
        "2\t.1.7\t 4\t  ab\tTEST",
    )
    cfg = websmart_snmp.parse(text)
    assert cfg.vlans == []
    assert any("ab" in w for w in cfg.warnings)


def test_short_bitmap_is_skipped_but_pvid_survives():
    text = _dump(
        f"@   1\t{_VLAN_STATIC}",
        "2\t.1.7\t 4\t   5\tVLAN7",
        # Declares 8 bytes but carries 2; taken at face value it would make
        # port 3 a member of vlan 7.
        "2\t.2.7\t 4\t   8\t\x20\x00",
        f"@   2\t{_PORT_VLAN}",
        "2\t.1.3\t66\t7",
    )
    cfg = websmart_snmp.parse(text)
    p3 = _port(cfg, "3")
    assert p3.access_vlan == 7  # PVID preserved
    assert p3.mode == "unknown"  # no trustworthy membership
    assert p3.trunk_allowed_vlans == []
    assert any("declared" in w for w in cfg.warnings)


def test_bitmap_decode_is_msb_first():
    text = _dump(
        f"@   1\t{_VLAN_STATIC}",
        "2\t.1.7\t 4\t   5\tVLAN7",
        "2\t.2.7\t 4\t   2\t\x80\x01",  # port 1 and port 16
    )
    cfg = websmart_snmp.parse(text)
    assert sorted(int(p.name) for p in cfg.ports) == [1, 16]
    assert cfg.warnings == []


def test_octet_string_containing_tab_and_cr_bytes():
    # A bitmap whose bytes include 0x09 (tab) and 0x0d (CR) must be read by
    # declared length, not by splitting or stripping the line.
    text = _dump(
        f"@   1\t{_VLAN_STATIC}",
        "2\t.1.7\t 4\t   5\tVLAN7",
        "2\t.2.7\t 4\t   2\t\x09\x0d",
    )
    cfg = websmart_snmp.parse(text)
    # 0x09 -> ports 5, 8; 0x0d -> ports 13, 14, 16
    assert sorted(int(p.name) for p in cfg.ports) == [5, 8, 13, 14, 16]
    assert cfg.warnings == []
