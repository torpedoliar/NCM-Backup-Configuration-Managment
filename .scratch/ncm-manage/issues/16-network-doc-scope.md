# 16: Tutup celah legacy — `GET /network-doc` ikut pola scope

**Latar:** Audit 2026-09-10: `GET /api/v1/network-doc` (2 endpoint) masih `require_api_key` (key-only TANPA scope) — satu-satunya endpoint yang belum ikut pola scope tiket 01/02. User menyetujui penutupan + meminta panduan migrasi produksi (generate API key baru).

**Desain:** `require_api_key` di network_doc.py → `require_key_or_jwt("read")` (pola sama dengan read endpoints lain). Key legacy (scopes NULL/[]) otomatis ditolak 403 di sini setelah perubahan — itu disengaja, dengan panduan migrasi: buat key baru berscope `read` di NCM (API Keys), pasang ke konsumen (DG Network Docs / curl), lalu revoke key lama. Update runbook DG + catatan di docs NCM.

**Blocked by:** None.

**Status:** done (commit 094e856; runbook DG bf8a90c)

- [x] network_doc.py memakai `require_key_or_jwt("read")` (JWT viewer+/operator tetap bisa baca).
- [x] pytest: key legacy (NULL scope) → 403 di /network-doc; key scope read → 200; JWT viewer → 200. (`test_network_doc_api.py`, matriks `test_scoped_api_keys.py` — suite 442 passed.)
- [x] Runbook DG + docs NCM: langkah migrasi produksi (generate key baru → pasang → revoke lama). Runbook DG section 8 + catatan tiket 16 di tab API Reference aplikasi.
- [x] Commit; suite hijau penuh.
