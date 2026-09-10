"""Anti-drift: the in-app API reference (web/src/api/apiReference.ts) must match
the live routers. Parses the generated TS data as JSON5-lite (regex extraction)
so the backend test suite needs no Node; the frontend `tsc -b` build guards the
TS itself. If a route is added/removed without regenerating apiReference.ts
(`scripts/gen_api_reference.py`), this test fails."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from unittest.mock import MagicMock  # noqa: E402

from app_v4.core.config import Settings  # noqa: E402
from app_v4.service.app import create_app  # noqa: E402
from app_v4.service.events import WEBHOOK_EVENT_MAP  # noqa: E402

API_REF_TS = REPO_ROOT / "app_v4" / "web" / "src" / "api" / "apiReference.ts"
WEBHOOK_TS = REPO_ROOT / "app_v4" / "web" / "src" / "api" / "webhookEvents.ts"


def _live_routes() -> set[tuple[str, str]]:
    runtime = MagicMock()
    runtime.settings = Settings(base_dir=str(REPO_ROOT))
    runtime.shutdown = lambda: None
    app = create_app(runtime)
    routes: set[tuple[str, str]] = set()
    for inc in app.routes:
        if type(inc).__name__ != "_IncludedRouter":
            continue
        for route in inc.original_router.routes:
            methods = getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}
            for method in methods:
                routes.add((method, "/api/v1" + route.path))
    return routes


def _ts_entries() -> set[tuple[str, str]]:
    text = API_REF_TS.read_text(encoding="utf-8")
    # Strip the API_REF array body, then pull { method, path } object literals.
    start = text.index("export const API_REF: ApiRefEntry[] = [")
    end = text.index("];", start)
    block = text[start:end]
    pattern = re.compile(
        r"method:\s*'([A-Z]+)',\s*path:\s*'([^']+)'",
    )
    return {(m, p) for m, p in pattern.findall(block)}


def _ts_descriptions() -> set[str]:
    text = API_REF_TS.read_text(encoding="utf-8")
    start = text.index("export const ENDPOINT_DESCRIPTIONS: Record<string, string> = {")
    end = text.index("};", start)
    return set(re.findall(r"'([A-Z]+ [^']+)':", text[start:end]))


def _ts_webhook_map() -> dict[str, list[str]]:
    text = WEBHOOK_TS.read_text(encoding="utf-8")
    data = {}
    for internal, names in re.findall(r"(\w+):\s*\[([^\]]*)\]", text):
        data[internal] = [n.strip().strip("'\"") for n in names.split(",") if n.strip()]
    return data


def test_api_reference_sync():
    live = _live_routes()
    documented = _ts_entries()
    assert live == documented, (
        "API reference drifted from routers.\n"
        "Missing from docs (add via scripts/gen_api_reference.py): "
        f"{sorted(live - documented)}\n"
        f"Stale in docs (remove): {sorted(documented - live)}"
    )
    assert len(live) >= 75, f"expected the full API surface documented, got {len(live)}"


def test_every_documented_endpoint_has_description():
    documented = _ts_entries()
    descriptions = _ts_descriptions()
    keys = {f"{m} {p}" for m, p in documented}
    assert keys <= descriptions, f"missing descriptions: {sorted(keys - descriptions)}"
    assert descriptions <= keys, f"orphan descriptions: {sorted(descriptions - keys)}"


def test_webhook_event_map_matches_backend():
    assert _ts_webhook_map() == {k: list(v) for k, v in WEBHOOK_EVENT_MAP.items()}


def test_known_scopes_documented():
    text = API_REF_TS.read_text(encoding="utf-8")
    from app_v4.data.repository import KNOWN_SCOPES

    for scope in sorted(KNOWN_SCOPES):
        # `read` is a bare TS key (unquoted); scoped names are quoted.
        pattern = rf"^(\s*{re.escape(scope)}|\s*'{re.escape(scope)}'):\s"
        assert re.search(pattern, text, re.M), f"scope {scope} missing from KNOWN_SCOPES docs"
