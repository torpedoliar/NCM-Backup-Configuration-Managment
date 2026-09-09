# Plan: Tiket 02 — NCM write scopes (switches/credentials/schedules/baselines + trigger backup)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DataGuard dapat mengelola penuh NCM lewat API key berscope: CRUD switch, set/update kredensial tanpa read-back, ubah jadwal, buat baseline, trigger backup on-demand. Tiap operasi tulis tertolak tanpa scope tepat (403), lolos dengan scope tepat.

**Architecture:** Perluas `KNOWN_SCOPES` dengan `switches:write`, `credentials:write`, `schedules:write`, `baselines:write`, `backup:write` (validasi + normalisasi sudah ada di `repository._normalize_scopes` — tambah set member saja). Endpoint tulis yang dibuka ke DG ganti `require_role(...)` → `require_key_or_jwt("<scope>")` — dependency gabungan dari tiket 01 (JWT path = peran terautentikasi mana pun, key path = scope tepat). Audit log mencatat aksi tanpa nilai password (sudah begitu untuk kredensial: `detail={"name": ...}` — pertahankan, tambah `scopes` TIDAK perlu di audit tulis). Kredensial: TIDAK ADA endpoint read-back — `CredentialOut` hanya (id, name, username, timestamps); verifikasi tidak ada perubahan response yang membocorkan password/enable_password. Trigger backup: dua alias POST (`/switches/{id}/backup` + `/switches/{id}/backups`) dibuka dengan scope `backup:write`.

**Tech Stack:** Python 3, FastAPI, async SQLAlchemy (SQLite), pytest + `fastapi.testclient.TestClient`. Stdlib only — no new dependencies.

**Spec:** `.scratch/ncm-manage/SPEC.md`. **Ticket:** `.scratch/ncm-manage/issues/02-ncm-write-scopes.md`. **Depends on:** tiket 01 (commit 4beb5ef).

## Global Constraints

- No new third-party dependencies — stdlib only.
- JWT lama tetap jalan di semua endpoint tulis yang dibuka (zero-downtime untuk UI desktop NCM yang pakai JWT).
- Key lama (tanpa scope) → 403 di semua endpoint tulis baru (tidak ada eskalasi diam-diam).
- Password/enable_password TIDAK PERNAH muncul di response, log, atau audit detail — ini security gate, bukan preferensi.
- API errors pakai `problem(status, title, detail)` (problem+json).
- Tests extend `app_v4/tests/test_scoped_api_keys.py` (tambah bagian write-matrix) + suite existing harus tetap hijau.
- ponytail: tanpa scope baru di luar 5 yang dispec; tanpa refactor auth tambahan — reuse `require_key_or_jwt` apa adanya.

## File Structure

Modified:
- `app_v4/data/repository.py` — tambah 5 scope ke `KNOWN_SCOPES` (satu baris).
- `app_v4/service/api/switches.py` — POST/PATCH/deactivate/activate/DELETE pakai `require_key_or_jwt("switches:write")`.
- `app_v4/service/api/credentials.py` — POST/PATCH/DELETE pakai `require_key_or_jwt("credentials:write")`; GET list tetap JWT-only (`require_role("admin","operator")` — username terlihat di response, bukan untuk key generik).
- `app_v4/service/api/jobs.py` — POST/PATCH/DELETE/run pakai `require_key_or_jwt("schedules:write")`; GET list dibuka `require_key_or_jwt("read")` (jadwal perlu terlihat dari DG).
- `app_v4/service/api/reviews.py` — POST /baselines, POST /baselines/{id}/refresh, DELETE /baselines pakai `require_key_or_jwt("baselines:write")`; GET /reviews/{id}/rollback dibuka `require_key_or_jwt("read")` (read-only generator, dibutuhkan DG untuk diff view). Review status/post-notes/promote/run-cycle TETAP JWT-only (persetujuan drift = aksi manusia via UI; dibuka di tiket 05 bila DG butuh — catat di ticket notes bila ditunda).
- `app_v4/service/api/backups.py` — 2 alias trigger POST pakai `require_key_or_jwt("backup:write")`; DELETE backup tetap JWT-only (destruktif, tidak dibutuhkan DG).
- `app_v4/tests/test_scoped_api_keys.py` — tambah write-matrix + no-readback assertions.
- `.scratch/ncm-manage/issues/02-ncm-write-scopes.md` — tandai done saat hijau.

Out of scope: webhook/HMAC (tiket 03), DG sisi klien (tiket 04+).

---

### Task 1: Perluas KNOWN_SCOPES + pasang di endpoint tulis

**Files:** semua Modified di atas kecuali test + ticket file.

**Interfaces:**
- Consumes: `require_key_or_jwt` (tiket 01), `KNOWN_SCOPES`, pola `problem()` existing.
- Produces: 5 scope baru valid di create API key; endpoint tulis terdaftar di atas menerima JWT lama ATAU key berscope tepat; key salah-scope/lama → 403; tanpa kredensial → 401.

- [ ] **Step 1: Write the failing test**

Append ke `app_v4/tests/test_scoped_api_keys.py`:

```python
@pytest.mark.asyncio
async def test_write_matrix_scopes(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        await Repository(session).create_user("admin", "h", "admin")
        await session.commit()
    client = TestClient(create_app(runtime))
    hdr = {"Authorization": f"Bearer {_admin_token(runtime)}"}

    def mk(name, scopes):
        r = client.post("/api/v1/api-keys", headers=hdr, json={"name": name, "scopes": scopes})
        assert r.status_code == 201, (name, r.text)
        return {"X-API-Key": r.json()["key"]}

    legacy = mk("legacy", [])
    sw = mk("sw", ["switches:write"])
    cred = mk("cred", ["credentials:write"])
    sched = mk("sched", ["schedules:write"])
    base = mk("base", ["baselines:write"])
    bak = mk("bak", ["backup:write"])

    # bootstrap: 1 credential + 1 switch via JWT (diperlukan untuk operasi lain)
    c = client.post("/api/v1/credentials", headers=hdr,
                    json={"name": "c1", "username": "u", "password": "p"}).json()
    s = client.post("/api/v1/switches", headers=hdr,
                    json={"name": "s1", "ip": "10.0.0.1", "protocol": "ssh",
                          "port": 22, "credential_id": c["id"]}).json()

    # switches:write membuka CRUD switch, scope lain ditolak
    assert client.post("/api/v1/switches", headers=sw,
                       json={"name": "s2", "ip": "10.0.0.2", "protocol": "ssh",
                             "port": 22, "credential_id": c["id"]}).status_code == 201
    assert client.post("/api/v1/switches", headers=cred,
                       json={"name": "sx", "ip": "10.0.0.9", "protocol": "ssh",
                             "port": 22, "credential_id": c["id"]}).status_code == 403
    assert client.post("/api/v1/switches", headers=legacy,
                       json={"name": "sy", "ip": "10.0.0.8", "protocol": "ssh",
                             "port": 22, "credential_id": c["id"]}).status_code == 403
    assert client.get("/api/v1/switches", headers=sw).status_code == 403  # write key tidak dapat read
    assert client.patch(f"/api/v1/switches/{s['id']}", headers=sw,
                        json={"notes": "via-dg"}).status_code == 200

    # credentials:write membuka set/update tanpa read-back
    r = client.post("/api/v1/credentials", headers=cred,
                    json={"name": "c2", "username": "u2", "password": "SECRET_PW",
                          "enable_password": "SECRET_EN"})
    assert r.status_code == 201
    body = r.text
    assert "SECRET_PW" not in body and "SECRET_EN" not in body
    cid = r.json()["id"]
    r2 = client.patch(f"/api/v1/credentials/{cid}", headers=cred, json={"password": "ROTATED_PW"})
    assert r2.status_code == 200
    assert "ROTATED_PW" not in r2.text
    listed = client.get("/api/v1/credentials", headers=hdr).json()
    assert all("password" not in k for row in listed for k in row.keys())

    # schedules:write membuka CRUD jadwal + GET jadwal ikut scope read
    j = client.post("/api/v1/jobs", headers=sched,
                    json={"switch_id": s["id"], "interval_minutes": 60}).json()
    assert j["id"] > 0
    assert client.patch(f"/api/v1/jobs/{j['id']}", headers=sched,
                        json={"interval_minutes": 30}).status_code == 200
    assert client.get("/api/v1/jobs", headers=sched).status_code == 403  # write-only key
    assert client.post("/api/v1/jobs", headers=sw,
                       json={"switch_id": s["id"], "interval_minutes": 60}).status_code == 403

    # baselines:write membuka buat baseline; butuh backup sukses — skip bila tak ada backup:
    # cukup verifikasi 403 untuk scope salah + 401/422 path (pembuatan penuh diuji tiket 07 E2E)
    assert client.post("/api/v1/baselines", headers=sw,
                       json={"kind": "switch", "switch_id": s["id"]}).status_code == 403
    assert client.post("/api/v1/baselines", headers=legacy,
                       json={"kind": "switch", "switch_id": s["id"]}).status_code == 403

    # backup:write membuka trigger, scope lain ditolak
    t = client.post(f"/api/v1/switches/{s['id']}/backup", headers=bak)
    assert t.status_code in (202, 422, 500), t.text  # 202 bila runner jalan; bukan 401/403
    assert client.post(f"/api/v1/switches/{s['id']}/backup", headers=sw).status_code == 403
    assert client.post(f"/api/v1/switches/{s['id']}/backup", headers=legacy).status_code == 403
```

Catatan: JWT lama tetap 200 di semua endpoint tulis di atas (dicover suite existing `test_*_api.py` — tidak perlu diulang di sini).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:/+SYNO+/Home/1. Project Windsurf/Test Project" && ./.venv/Scripts/python.exe -m pytest app_v4/tests/test_scoped_api_keys.py::test_write_matrix_scopes -q -p no:warnings`
Expected: FAIL (scope baru unknown → 422 saat create key; endpoint tulis belum kenal key).

- [ ] **Step 3: Write minimal implementation**

1. `repository.py`: `KNOWN_SCOPES = frozenset({"read", "switches:write", "credentials:write", "schedules:write", "baselines:write", "backup:write"})`.
2. Ganti `require_role(...)` → `require_key_or_jwt("<scope>")` HANYA di endpoint yang terdaftar di File Structure (per-file daftar di atas). Import `require_key_or_jwt` di tiap file; `AccessClaims`/`actor` tetap dipakai untuk audit (jangan hapus — audit butuh `actor.user_id`... PERHATIAN: key path tidak punya user_id! Lihat Step 3b).
3. **Step 3b — audit tanpa user (PENTING):** endpoint yang dibuka ke key tidak lagi punya `AccessClaims`. Ganti `actor: AccessClaims = Depends(...)` menjadi `_auth: str = Depends(require_key_or_jwt(...))` + ambil audit user id via helper: bila JWT, verifikasi ulang dan pakai `claims.user_id`; bila key (`key:<name>`), pakai `user_id=None` (kolom nullable — cek model AuditLog: `user_id` nullable=True ✓) dan tambah `"key": <name>` ke audit detail. Implementasikan helper di `deps.py`: `audit_identity(auth: str, request) -> tuple[int | None, dict]` — JWT → (user_id, {}), key → (None, {"key": name}). Semua endpoint yang diubah memakai helper ini untuk `audit_writer.record`.
4. `reviews.py` rollback GET dibuka ke `"read"` (satu baris).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:/+SYNO+/Home/1. Project Windsurf/Test Project" && ./.venv/Scripts/python.exe -m pytest app_v4/tests/test_scoped_api_keys.py app_v4/tests/test_api_keys.py app_v4/tests/test_switches_api.py app_v4/tests/test_credentials_api.py app_v4/tests/test_jobs_api.py app_v4/tests/test_backups_api.py -q -p no:warnings`
Expected: PASS semua.

- [ ] **Step 5: Run full suite + commit**

Run: full suite `python -m pytest app_v4/tests/ -q -p no:warnings` (harus hijau semua).
Run: `git add -A && git commit -m "feat: write scopes for DG management (ticket 02)"`
Tandai tiket 02 done di `.scratch/ncm-manage/issues/02-ncm-write-scopes.md`.
Do NOT push without explicit consent.
