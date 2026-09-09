# 01: NCM scoped API keys + combined auth

**What to build:**
Admin NCM dapat membuat API key dengan scope granular dari UI/API NCM. Key berscope `read` membuka endpoint read (GET switches/backups/reviews); key TANPA scope tetap hanya bisa network-doc — tidak ada regresi untuk integrasi DataGuard yang ada. Auth dependency gabungan JWT-atau-API-key dipasang di semua router yang relevan.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Model API key punya kolom `scopes` (list scope).
- [ ] Matrix test scope×endpoint: key tiap scope vs tiap endpoint — hasil sesuai desain (hijau).
- [ ] Key lama (tanpa kolom scope / kosong) berperilaku persis seperti sekarang (hanya network-doc) — regresi test hijau.
- [ ] Endpoint read mengembalikan 403 tanpa scope `read`; 200 dengan scope `read`.