# 01: NCM scoped API keys + combined auth

**What to build:**
Admin NCM dapat membuat API key dengan scope granular dari UI/API NCM. Key berscope `read` membuka endpoint read (GET switches/backups/reviews); key TANPA scope tetap hanya bisa network-doc — tidak ada regresi untuk integrasi DataGuard yang ada. Auth dependency gabungan JWT-atau-API-key dipasang di semua router yang relevan.

**Blocked by:** None (can start immediately).

**Status:** done (commit 4beb5ef)

- [x] Model API key punya kolom `scopes` (list scope).
- [x] Matrix test scope×endpoint: key tiap scope vs tiap endpoint — hasil sesuai desain (hijau).
- [x] Key lama (tanpa kolom scope / kosong) berperilaku persis seperti sekarang (hanya network-doc) — regresi test hijau.
- [x] Endpoint read mengembalikan 403 tanpa scope `read`; 200 dengan scope `read`.

**Notes:**
- Plan: `docs/superpowers/plans/2026-09-09-ticket-01-scoped-api-keys.md`.
- `GET /reviews/{id}/rollback` (remediation CLI generator) sengaja tetap JWT-only — write-adjacent, dibuka di tiket 02 bila dibutuhkan.
- `network-doc` key-only by design (JWT 401 di sana) — kontrak didokumentasikan di test, bukan diubah.
- Full suite: 424 passed.
