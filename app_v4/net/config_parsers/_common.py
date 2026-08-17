from __future__ import annotations


def expand_id_list(spec: str) -> list[int]:
    """Expand a VLAN/port id spec like '4-6,8-12,88' into a flat int list."""
    out: list[int] = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def expand_ports_gN(spec: str) -> list[str]:
    """Expand a Dell range spec '1-3,6' into ['g1','g2','g3','g6']."""
    return [f"g{n}" for n in expand_id_list(spec)]
