"""Dump the NCM REST API surface as JSON: [{method, path, tag, auth, summary}].

Anti-stale by design: the companion pytest (test_api_reference_sync) imports
this module and diffs (method, path) against create_app()'s live routes, so a
router change without a docs touch fails the suite instead of rotting silently.

Auth labels come from require_* dependency closures (freevars: scopes /
allowed_roles+scope), falling back to the endpoint signature default. Either
way the set of endpoints — the drift-critical part — comes from the routers.

Stdlib only. Run from the repo root:
    ./.venv/Scripts/python.exe scripts/gen_api_reference.py
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from unittest.mock import MagicMock  # noqa: E402

from app_v4.core.config import Settings  # noqa: E402
from app_v4.data.repository import KNOWN_SCOPES  # noqa: E402
from app_v4.service.app import create_app  # noqa: E402
from app_v4.service.events import WEBHOOK_EVENT_MAP  # noqa: E402

API_PREFIX = "/api/v1"


def describe_auth(fn) -> str | None:
    """Auth label from a require_* factory product, or None when unrelated."""
    name = getattr(fn, "__name__", "") or ""
    if name == "require_api_key":
        return "API key (any)"
    if name == "require_user":
        return "JWT (any role)"
    code = getattr(fn, "__code__", None)
    if code is None:
        return None
    freevars = code.co_freevars or ()
    cells = [c.cell_contents for c in (getattr(fn, "__closure__", None) or ())]
    # require_role_or_key's dependency closes over (key_dep, role_dep); the
    # roles/scope live one closure deeper (inside require_key_or_jwt / require_role).
    if "key_dep" in freevars:
        inner = cells[freevars.index("key_dep")]
        icode = getattr(inner, "__code__", None)
        icells = [c.cell_contents for c in (getattr(inner, "__closure__", None) or ())]
        roles = None
        scope = None
        if icode is not None and "scopes" in (icode.co_freevars or ()):
            scope = icells[(icode.co_freevars or ()).index("scopes")]
        if "role_dep" in freevars:
            role_dep = cells[freevars.index("role_dep")]
            rcode = getattr(role_dep, "__code__", None)
            rcells = [c.cell_contents for c in (getattr(role_dep, "__closure__", None) or ())]
            if rcode is not None and "allowed_roles" in (rcode.co_freevars or ()):
                roles = rcells[(rcode.co_freevars or ()).index("allowed_roles")]
        if roles and scope:
            scope_str = scope[0] if isinstance(scope, (tuple, list)) else scope
            return "JWT %s or key %s" % ("/".join(roles), scope_str)
        if scope:
            scope_str = scope[0] if isinstance(scope, (tuple, list)) else scope
            return "JWT-or-key (scope: %s)" % scope_str
    if name == "dependency" and "scopes" in freevars:
        scopes = cells[freevars.index("scopes")]
        return "JWT-or-key (scope: %s)" % ", ".join(sorted(scopes))
    if name == "dependency" and "allowed_roles" in freevars and "scope" in freevars:
        roles = cells[freevars.index("allowed_roles")]
        return "JWT %s or key %s" % ("/".join(roles), cells[freevars.index("scope")])
    if name == "dependency" and "allowed_roles" in freevars:
        return "JWT (%s)" % "/".join(cells[freevars.index("allowed_roles")])
    mapping = {
        "require_key_or_jwt": "JWT-or-key",
        "require_role_or_key": "JWT-or-key (scoped)",
        "require_role": "JWT",
        "require_scoped_key": "API key (scoped)",
    }
    return mapping.get(name)


def endpoint_auth(route) -> str:
    """Auth label from the endpoint's signature Depends defaults."""
    params = list(inspect.signature(route.endpoint).parameters.values())
    labels = []
    for param in params:
        dep = getattr(param.default, "dependency", None)
        if dep is None:
            continue
        label = describe_auth(dep)
        if label and label not in labels:
            labels.append(label)
    if labels:
        return "; ".join(labels)
    # No Depends(...) at all: login/refresh/logout take plain body params.
    return "public (no credentials)"


def collect_routes() -> list[dict]:
    runtime = MagicMock()
    runtime.settings = Settings(base_dir=str(REPO_ROOT))
    runtime.shutdown = lambda: None
    app = create_app(runtime)
    seen: dict[tuple[str, str], dict] = {}
    for inc in app.routes:
        if type(inc).__name__ != "_IncludedRouter":
            continue
        for route in inc.original_router.routes:
            methods = sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"})
            if not methods:
                continue
            path = API_PREFIX + route.path
            tags = list(getattr(route, "tags", None) or [])
            for method in methods:
                seen[(method, path)] = {
                    "method": method,
                    "path": path,
                    "tag": tags[0] if tags else "",
                    "auth": endpoint_auth(route),
                    "summary": getattr(route, "summary", None) or route.endpoint.__name__,
                }
    return [seen[k] for k in sorted(seen)]


def main() -> None:
    entries = collect_routes()
    print(f"# NCM API surface: {len(entries)} endpoints")
    print(f"# KNOWN_SCOPES: {sorted(KNOWN_SCOPES)}")
    print(f"# WEBHOOK_EVENT_MAP: {WEBHOOK_EVENT_MAP}")
    print(json.dumps(entries, indent=2))


if __name__ == "__main__":
    main()
