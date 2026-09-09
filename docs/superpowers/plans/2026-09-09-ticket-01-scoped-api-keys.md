# Plan: Tiket 01 — NCM scoped API keys + combined auth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** API key NCM mendukung scope granular. Key dengan scope `read` membuka endpoint read DataGuard (GET switches/backups/reviews GET); key TANPA scope (lama) tetap hanya bisa network-doc — tidak ada regresi.

**Architecture:** Kolom `scopes` baru (JSON text, whitelist scope) di model `ApiKey` — tabel dibuat `Base.metadata.create_all` via `init_db`, tanpa Alembic/migrasi manual (mengikuti preseden network-doc plan 2026-08-17: "New `ApiKey` table is created by `Base.metadata.create_all`"). `require_api_key` diperluas jadi `require_scoped_key(*scopes)`: verifikasi hash key seperti sekarang, lalu cek scope; key lama (scopes kosong/NULL) hanya lolos untuk network-doc. Dependency gabungan `require_key_or_jwt` dipasang di router read yang relevan. Waktu migrasi kolom baru di DB lama (file SQLite existing): `create_all` tidak menambah kolom ke tabel yang sudah ada — tambah `ALTER TABLE api_keys ADD COLUMN scopes` yang idempotent di `init_db` (cek PRAGMA dulu, skip bila kolom sudah ada).

**Tech Stack:** Python 3, FastAPI, async SQLAlchemy (SQLite), pytest + `fastapi.testclient.TestClient`. Stdlib only (`json`) — no new dependencies.

**Spec:** `.scratch/ncm-manage/SPEC.md` (Implementation Decisions: NCM auth). **Ticket:** `.scratch/ncm-manage/issues/01-ncm-scoped-api-keys.md`.

## Global Constraints

- No new third-party dependencies — stdlib only.
- DB lama harus tetap jalan: tambah kolom via ALTER idempotent, bukan create_all saja (create_all tidak mengubah tabel existing).
- Key lama (scopes NULL/kosong) berperilaku persis seperti sekarang (hanya network-doc) — ini regresi gate.
- API errors pakai `app_v4.service.problem.problem(status, title, detail)` (problem+json), konsisten dengan router existing.
- Auth/audit mengikuti konvensi `app_v4/service/api/api_keys.py`: `require_role`, `get_db`, `get_runtime`, `runtime.audit_writer.record(...)`.
- Tests extend `app_v4/tests` pytest suite (fixtures `test_settings`, `session_factory` dari `conftest.py`; `ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s"*32)`).
- Scope yang tidak dikenal saat create → 422, bukan disimpan mentah.
- Scope disimpan sebagai JSON array di kolom TEXT; normalisasi (lowercase, strip, dedupe, sort) di satu tempat (repository).
- ponytail: tanpa tabel baru, tanpa kolom per-scope boolean, tanpa library validasi baru — satu kolom TEXT + satu set konstanta scope.

## File Structure

New:
- `app_v4/tests/test_scoped_api_keys.py` — matrix test scope×endpoint + regresi key lama + create/list dengan scopes.

Modified:
- `app_v4/data/models.py` — tambah `ApiKey.scopes` (TEXT nullable, default NULL = key lama).
- `app_v4/data/repository.py` — `create_api_key(..., scopes=None)`; normalisasi scope di sini.
- `app_v4/data/db.py` — ALTER TABLE idempotent untuk `scopes` di `init_db`.
- `app_v4/service/deps.py` — `require_scoped_key(*scopes)` + `require_key_or_jwt(*scopes)` (gabungan JWT-atau-key); `require_api_key` tetap (dipakai network-doc, perilaku tak berubah).
- `app_v4/service/api/api_keys.py` — `ApiKeyCreate.scopes`, `ApiKeyCreated.scopes`, `ApiKeyOut.scopes`.
- `app_v4/service/api/switches.py` — GET list/detail pakai `require_key_or_jwt("read")`.
- `app_v4/service/api/backups.py` — GET list/detail/diff/content pakai `require_key_or_jwt("read")`.
- `app_v4/service/api/reviews.py` — GET baselines/reviews/diff pakai `require_key_or_jwt("read")`.

Out of scope (tiket 02/03): write scopes enforcement di endpoint tulis, webhook/HMAC.

---

### Task 1: Model + repository + migrasi kolom

**Files:**
- Modify: `app_v4/data/models.py` (tambah kolom `scopes`)
- Modify: `app_v4/data/repository.py` (`create_api_key` terima `scopes`)
- Modify: `app_v4/data/db.py` (ALTER TABLE idempotent)
- Test: `app_v4/tests/test_scoped_api_keys.py` (bagian 1: persistensi scope)

**Interfaces:**
- Consumes: `ApiKey` existing (id, name, key_hash, prefix, created_at, last_used_at, revoked).
- Produces:
  - `ApiKey.scopes: Mapped[Optional[str]]` — JSON array string, nullable, default None.
  - `KNOWN_SCOPES = frozenset({"read"})` di `repository.py` (tiket 02 menambah write scopes di set ini).
  - `Repository.create_api_key(name, key_hash, prefix, scopes: list[str] | None = None) -> ApiKey` — normalisasi: lowercase/strip/dedupe/sort; raise `ValueError` bila ada scope tak dikenal; `None`/kosong → simpan NULL.
  - `Repository.get_api_key_scopes(key: ApiKey) -> list[str]` — parse JSON, rusak/kosong → `[]`.
  - `init_db` menjalankan `ALTER TABLE api_keys ADD COLUMN scopes TEXT` hanya bila kolom belum ada (cek `PRAGMA table_info(api_keys)`), aman di SQLite lama maupun DB baru dari create_all.

- [ ] **Step 1: Write the failing test**

Create `app_v4/tests/test_scoped_api_keys.py` (bagian 1):

```python
import json
import pytest
from app_v4.data.repository import Repository, KNOWN_SCOPES


@pytest.mark.asyncio
async def test_create_key_with_read_scope_persists_normalized(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        key = await repo.create_api_key(
            name="dg", key_hash="h" * 64, prefix="ncr_abcd", scopes=["read", " READ "]
        )
        await session.commit()
        assert json.loads(key.scopes) == ["read"]


@pytest.mark.asyncio
async def test_unknown_scope_raises(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        with pytest.raises(ValueError):
            await repo.create_api_key(name="bad", key_hash="x" * 64, prefix="ncr_bad", scopes=["root"])


@pytest.mark.asyncio
async def test_legacy_key_has_empty_scopes(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        key = await repo.create_api_key(name="legacy", key_hash="y" * 64, prefix="ncr_leg")
        await session.commit()
        assert repo.get_api_key_scopes(key) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:/+SYNO+/Home/1. Project Windsurf/Test Project" && python -m pytest app_v4/tests/test_scoped_api_keys.py -x -q`
Expected: FAIL (no `scopes` column / `create_api_key` takes no `scopes` kwarg).

- [ ] **Step 3: Write minimal implementation**

1. `models.py`: tambah di `ApiKey`: `scopes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)`.
2. `repository.py`: `KNOWN_SCOPES = frozenset({"read"})`; `create_api_key(..., scopes=None)` normalisasi + `ValueError` untuk scope tak dikenal; `get_api_key_scopes(key)` parse aman.
3. `db.py`: di `init_db` setelah `create_all`, cek `PRAGMA table_info(api_keys)`; bila tak ada kolom `scopes`, eksekusi `ALTER TABLE api_keys ADD COLUMN scopes TEXT`.

- [ ] **Step 4: Run test to verify it passes**

Run: same pytest as Step 2.
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

Run: `cd "D:/+SYNO+/Home/1. Project Windsurf/Test Project" && git add app_v4/data/models.py app_v4/data/repository.py app_v4/data/db.py app_v4/tests/test_scoped_api_keys.py && git commit -m "feat: scoped API keys model + repo + idempotent migration"`
Do NOT push without explicit consent.

---

### Task 2: Deps gabungan + pasang di endpoint read

**Files:**
- Modify: `app_v4/service/deps.py` (`require_scoped_key`, `require_key_or_jwt`)
- Modify: `app_v4/service/api/api_keys.py` (scopes di create/list response)
- Modify: `app_v4/service/api/switches.py` (GET list/detail)
- Modify: `app_v4/service/api/backups.py` (GET list/detail/diff/content)
- Modify: `app_v4/service/api/reviews.py` (GET baselines/reviews/diff)
- Test: `app_v4/tests/test_scoped_api_keys.py` (bagian 2: matrix HTTP)

**Interfaces:**
- Consumes: `require_api_key` (tak berubah, tetap dipakai network-doc), `require_role`, `require_user`, `Repository.get_api_key_scopes`.
- Produces:
  - `require_scoped_key(*scopes: str)` — FastAPI dependency: verifikasi key persis seperti `require_api_key` (X-API-Key atau Bearer), lalu: bila endpoint meminta scope dan key berscopes kosong → 403; bila key punya ≥1 scope yang diminta → lolos, return key name. (`require_api_key` tetap untuk network-doc: key lama tanpa scope tetap 200 di sana.)
  - `require_key_or_jwt(*scopes: str)` — lolos bila JWT valid (role apa pun yang endpoint izinkan — dependency ini gantikan `require_role` di endpoint read yang dipasang) ATAU key berscope tepat. JWT path: verifikasi via `runtime.auth_service.verify_access_token`, tanpa cek role (endpoint read terbuka untuk semua role terautentikasi, sama seperti sebelum: admin/operator/viewer). Key path: seperti `require_scoped_key`. Gagal keduanya → 401 bila tak ada kredensial sama sekali, 403 bila kredensial ada tapi tak berhak.
  - `ApiKeyCreate.scopes: list[str] = []`, `ApiKeyCreated.scopes: list[str]`, `ApiKeyOut.scopes: list[str]` (list kosong untuk key lama).
  - Endpoint yang dipasang: `GET /switches`, `GET /switches/{id}`, `GET /backups`, `GET /backups/latest-per-switch`, `GET /backups/{id}`, `GET /backups/{id}/content`, `GET /backups/{id}/decode`, `GET /backups/{id}/diff`, `GET /backups/diff`, `GET /backups/diff/side-by-side`, `GET /backups/report`, `GET /baselines`, `GET /reviews`, `GET /reviews/{id}/diff`, `GET /reviews/compliance`, `GET /reviews/compliance/report`. Endpoint tulis (POST/PATCH/DELETE) TIDAK disentuh — tetap JWT-only sampai tiket 02.

- [ ] **Step 1: Write the failing test**

Append ke `app_v4/tests/test_scoped_api_keys.py` (bagian 2) — pola mengikuti `test_api_keys.py` (`ServiceRuntime.for_tests`, `TestClient(create_app(runtime))`):

```python
import pytest
from fastapi.testclient import TestClient
from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


def _mk_client(runtime):
    return TestClient(create_app(runtime))


@pytest.mark.asyncio
async def test_matrix_scope_x_endpoint(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    client = _mk_client(runtime)
    hdr = {"Authorization": f"Bearer {runtime.auth_service.issue_access_token(1, 'admin', 'admin')}"}
    read_key = client.post("/api/v1/api-keys", headers=hdr, json={"name": "dg", "scopes": ["read"]}).json()["key"]
    legacy_key = client.post("/api/v1/api-keys", headers=hdr, json={"name": "legacy"}).json()["key"]

    read_endpoints = ["/api/v1/switches", "/api/v1/backups", "/api/v1/baselines", "/api/v1/reviews"]
    for ep in read_endpoints:
        assert client.get(ep, headers={"X-API-Key": read_key}).status_code == 200
        assert client.get(ep, headers={"X-API-Key": legacy_key}).status_code == 403
    # network-doc regresi: key lama tetap 200
    assert client.get("/api/v1/network-doc", headers={"X-API-Key": legacy_key}).status_code == 200
    assert client.get("/api/v1/network-doc", headers={"X-API-Key": read_key}).status_code == 200
    # JWT lama tetap jalan di semua endpoint read
    for ep in read_endpoints + ["/api/v1/network-doc"]:
        assert client.get(ep, headers=hdr).status_code == 200
    # tanpa kredensial tetap 401
    assert client.get("/api/v1/switches").status_code == 401


@pytest.mark.asyncio
async def test_create_lists_scopes(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        await Repository(session).create_user("admin", "h", "admin")
        await session.commit()
    client = _mk_client(runtime)
    hdr = {"Authorization": f"Bearer {runtime.auth_service.issue_access_token(1, 'admin', 'admin')}"}
    created = client.post("/api/v1/api-keys", headers=hdr, json={"name": "dg", "scopes": ["read"]})
    assert created.status_code == 201
    assert created.json()["scopes"] == ["read"]
    listed = client.get("/api/v1/api-keys", headers=hdr)
    assert listed.status_code == 200
    assert listed.json()[0]["scopes"] == ["read"]
    bad = client.post("/api/v1/api-keys", headers=hdr, json={"name": "bad", "scopes": ["root"]})
    assert bad.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:/+SYNO+/Home/1. Project Windsurf/Test Project" && python -m pytest app_v4/tests/test_scoped_api_keys.py -x -q`
Expected: FAIL (endpoint belum kenal scope; create belum terima `scopes`).

- [ ] **Step 3: Write minimal implementation**

1. `deps.py`: tambah `require_scoped_key(*scopes)` dan `require_key_or_jwt(*scopes)` sesuai Interfaces. Reuse logika lookup hash dari `require_api_key` (refactor ke helper privat `_lookup_key(...)` bila memungkinkan tanpa mengubah perilaku `require_api_key`).
2. `api_keys.py`: `ApiKeyCreate.scopes: list[str] = Field(default_factory=list)`; validasi terhadap `KNOWN_SCOPES`, tak dikenal → `problem(422, ...)`; `ApiKeyCreated`/`ApiKeyOut` tambah `scopes: list[str]` (parse via `repo.get_api_key_scopes`).
3. Pasang `Depends(require_key_or_jwt("read"))` menggantikan `Depends(require_role(...))` HANYA di endpoint GET yang terdaftar di Interfaces (switches/backups/reviews). `network_doc.py` TIDAK disentuh.
4. Audit `apikey.created` tambah `"scopes"` di detail (tanpa nilai key).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:/+SYNO+/Home/1. Project Windsurf/Test Project" && python -m pytest app_v4/tests/test_scoped_api_keys.py app_v4/tests/test_api_keys.py app_v4/tests/test_network_doc_api.py -q`
Expected: PASS semua (matrix hijau + regresi lama hijau).

- [ ] **Step 5: Run full suite + commit**

Run: `cd "D:/+SYNO+/Home/1. Project Windsurf/Test Project" && python -m pytest app_v4/tests/ -q` (418 tests harus hijau; bila ada Vitest, jalankan juga).
Run: `git add -A && git commit -m "feat: scoped API keys + combined JWT-or-key auth on read endpoints"`
Do NOT push without explicit consent.
