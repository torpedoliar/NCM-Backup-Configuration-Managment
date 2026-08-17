from pathlib import Path

from app_v4.net.config_parsers import dell

FIXTURE = Path(__file__).parent / "fixtures" / "network_doc" / "dell.txt"


def _port(cfg, name):
    return next(p for p in cfg.ports if p.name == name)


def test_dell_hostname_and_vlan_names():
    cfg = dell.parse(FIXTURE.read_text(encoding="utf-8"))
    assert cfg.hostname == "Office-1"
    names = {v.id: v.name for v in cfg.vlans}
    assert names[4] == "BOD"
    assert names[88] == "IPH-DEVICE"


def test_dell_access_port_from_range():
    # g7 -> 'switchport access vlan 4'
    cfg = dell.parse(FIXTURE.read_text(encoding="utf-8"))
    p = _port(cfg, "g7")
    assert p.mode == "access"
    assert p.access_vlan == 4


def test_dell_trunk_uplink_allowed_accumulates():
    # g24 is in many 'interface range ethernet g(22-24)' allowed-add blocks
    cfg = dell.parse(FIXTURE.read_text(encoding="utf-8"))
    p = _port(cfg, "g24")
    assert p.mode == "trunk"
    for vlan in (4, 6, 8, 9, 10, 11, 12):
        assert vlan in p.trunk_allowed_vlans


def test_dell_clean_fixture_produces_no_warnings():
    cfg = dell.parse(FIXTURE.read_text(encoding="utf-8"))
    assert cfg.warnings == []


def test_dell_exit_ends_block_so_orphaned_lines_are_dropped():
    # dell.txt carries editing damage: 'switchport trunk allowed vlan add 20'
    # (line 128) and 'description KeAt8724' (line 65) both sit after an 'exit'
    # with no interface line of their own. Without the exit reset they would
    # leak onto the preceding block's ports.
    cfg = dell.parse(FIXTURE.read_text(encoding="utf-8"))
    assert _port(cfg, "g20").trunk_allowed_vlans == [4, 14, 15, 18, 24]
    assert _port(cfg, "g23").description is None


def test_dell_unrecognised_interface_form_resets_block_context():
    # LAGs and slot syntax are routine on Dell PowerConnect. An interface form
    # we do not model must not inherit the previous block's ports.
    cfg = dell.parse(
        "interface range ethernet g(1-2)\n"
        "switchport trunk allowed vlan add 7\n"
        "interface port-channel 1\n"
        "switchport trunk allowed vlan add 99\n"
        "description lag-uplink\n"
        "exit\n"
        "interface ethernet 1/g5\n"
        "switchport access vlan 42\n"
        "exit\n"
    )
    for name in ("g1", "g2"):
        p = _port(cfg, name)
        assert p.trunk_allowed_vlans == [7]
        assert p.description is None
        assert p.access_vlan is None
    # the unmodelled blocks create no ports of their own
    assert {p.name for p in cfg.ports} == {"g1", "g2"}


def test_dell_allowed_vlan_add_accepts_list_and_range_forms():
    cfg = dell.parse(
        "interface ethernet g1\n"
        "switchport trunk allowed vlan add 4,6-8\n"
        "switchport trunk allowed vlan add 8,20\n"
        "exit\n"
    )
    p = _port(cfg, "g1")
    assert p.trunk_allowed_vlans == [4, 6, 7, 8, 20]
    assert p.mode == "trunk"
    assert cfg.warnings == []


def test_dell_malformed_vlan_id_warns_instead_of_raising():
    cfg = dell.parse(
        "hostname X\n"
        "interface range ethernet g(1-2)\n"
        "description uplink\n"
        "switchport trunk allowed vlan add 7\n"
        "switchport access vlan abc\n"
        "switchport trunk native vlan xx\n"
        "switchport trunk allowed vlan add zz\n"
        "exit\n"
        "interface vlan nope\n"
        "name Orphan\n"
        "exit\n"
    )
    # the good lines still land -- the result is partial, not lost
    assert cfg.hostname == "X"
    p = _port(cfg, "g1")
    assert p.description == "uplink"
    assert p.trunk_allowed_vlans == [7]
    # the malformed lines are skipped rather than applied or raised
    assert p.access_vlan is None
    assert p.native_vlan is None
    # a vlan block with an unparsable id yields no VlanDoc, not a crash
    assert cfg.vlans == []
    assert len(cfg.warnings) == 4
    assert all("unparsable vlan id" in w for w in cfg.warnings)


def test_dell_multiple_add_lines_in_one_block_accumulate():
    # 'add' is an accumulating verb: every add line extends the allowed set
    cfg = dell.parse(
        "interface range ethernet g(1-2)\n"
        "switchport trunk allowed vlan add 10\n"
        "switchport trunk allowed vlan add 20\n"
        "switchport trunk allowed vlan add 20\n"
        "exit\n"
        "interface ethernet g1\n"
        "switchport trunk allowed vlan add 30\n"
        "exit\n"
    )
    assert _port(cfg, "g1").trunk_allowed_vlans == [10, 20, 30]
    assert _port(cfg, "g2").trunk_allowed_vlans == [10, 20]
