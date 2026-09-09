# 02: NCM write scopes: switches/credentials/schedules/baselines + trigger backup

**What to build:**
DataGuard bisa mengelola penuh NCM lewat API: CRUD switch, set/update kredensial switch (plaintext diterima sekali, disimpan terenkripsi DPAPI, tidak ada endpoint read-back), ubah jadwal backup, buat golden baseline dari backup terakhir, dan trigger backup on-demand per switch. Semua lewat API key dengan write scope yang sesuai (`switches:write`, `credentials:write`, `schedules:write`, `baselines:write`, `backup:write`).

**Blocked by:** 1: NCM scoped API keys + combined auth.

**Status:** done (commit 33df745)

- [x] CRUD switch via API key `switches:write`; tanpa scope = 403.
- [x] Set/update kredensial menerima plaintext sekali jalan; tersimpan terenkripsi; TIDAK ADA endpoint yang mengembalikan plaintext (audit: aksi tercatat tanpa nilai).
- [x] Update jadwal via `schedules:write`; buat baseline via `baselines:write`.
- [x] Trigger backup on-demand via `backup:write`.
- [x] Semua operasi tulis tercatat di audit log NCM (tanpa nilai password).

**Notes:**
- Plan: `docs/superpowers/plans/2026-09-09-ticket-02-write-scopes.md`.
- Endpoint tulis yang dibuka memakai `require_role_or_key(*roles, scope=...)` — JWT callers TETAP di-check role seperti sebelumnya (operator tidak mendapat akses baru); key callers butuh scope tepat. `require_key_or_jwt` tanpa role-check hanya untuk GET read.
- `GET /jobs` dan `GET /baselines` dibuka ke scope `read` (DG butuh menampilkan jadwal/baseline).
- `GET /reviews/{id}/rollback` dibuka ke scope `read` (generator CLI, read-only).
- Review status/approve (POST /reviews/{id}/status, promote-baseline, run-cycle) TETAP JWT-only — keputusan drift = aksi manusia via UI; dibuka di tiket 05 bila DG butuh approve dari sentral.
- Audit: key-based writes dicatat dengan user_id NULL + `{"key": "<name>"}` di detail; JWT tetap user_id asli.
- Full suite: 430 passed.
