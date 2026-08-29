from app_v4.net.config_parsers._common import expand_id_list, expand_ports_gN


def test_expand_id_list_mixed_ranges_and_singles():
    assert expand_id_list("4-6,8-12,88") == [4, 5, 6, 8, 9, 10, 11, 12, 88]


def test_expand_id_list_ignores_spaces_and_empty():
    assert expand_id_list(" 1 , 3-4 ,") == [1, 3, 4]


def test_expand_ports_gN():
    assert expand_ports_gN("1-3,6") == ["g1", "g2", "g3", "g6"]


def test_expand_id_list_skips_malformed_parts():
    assert expand_id_list("4-,8,x,9") == [8, 9]

def test_expand_id_list_wholly_malformed_returns_empty():
    assert expand_id_list("x,–,4-") == []
