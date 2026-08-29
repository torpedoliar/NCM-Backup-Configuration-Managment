from __future__ import annotations


def vlan_id_from_token(cfg, token: str, line: str) -> int | None:
    """Coerce a vlan-id token to int, warning instead of raising on garbage."""
    try:
        return int(token)
    except ValueError:
        cfg.warnings.append(f"unparsable vlan id {token!r} in line: {line}")
        return None


def expand_id_list(spec: str) -> list[int]:
    """Expand a VLAN/port id spec like '4-6,8-12,88' into a flat int list.

    Lenient by contract: never raises on malformed input. Each comma-separated
    part is stripped individually (so tabs, CRs and newlines inside a wrapped
    device listing are tolerated), and any part that does not parse as an int
    -- or a range whose bounds do not parse, e.g. '4-' or 'x' -- is skipped.
    A wholly malformed spec yields an empty list.
    """
    out: list[int] = []
    for raw in spec.split(","):
        part = raw.strip()
        if not part:
            continue
        try:
            if "-" in part:
                lo, hi = part.split("-", 1)
                out.extend(range(int(lo), int(hi) + 1))
            else:
                out.append(int(part))
        except ValueError:
            continue
    return out


def expand_ports_gN(spec: str) -> list[str]:
    """Expand a Dell range spec '1-3,6' into ['g1','g2','g3','g6']."""
    return [f"g{n}" for n in expand_id_list(spec)]
