# 15: Dokumentasi API NCM dalam aplikasi — update ke API terbaru

**Latar:** Dokumen API terakhir yang user-facing adalah handoff network-doc (Agustus, sebelum scoped keys). Sejak tiket 01-08 API berubah besar: scopes per endpoint, auth ganda JWT-or-key, webhook HMAC, endpoint baru. User minta dokumentasi API **di dalam aplikasi** mengikuti API terbaru.

**Desain:** Static reference page di dalam NCM (bukan OpenAPI dump mentah): tabel endpoint per modul (switches, backups, credentials, jobs, baselines/reviews, network-doc, system, api-keys, auth, users, audit) dengan kolom **method, path, auth (JWT role / API-key scope / keduanya), deskripsi singkat**, plus bagian auth (cara kerja `X-API-Key`/Bearer, daftar KNOWN_SCOPES dan maknanya, pola legacy key), bagian webhook (event map + header X-NCM-Signature), dan contoh curl per modul. Sumber kebenaran: kode router `app_v4/service/api/*.py` (generate tabel dari decorator, bukan ketik manual, agar tidak basi lagi).

**Blocked by:** 01-08 (semua done).

**Status:** done (commit 094e856)

- [x] Halaman dokumentasi API di aplikasi (web NCM) merinci ≥75 endpoint aktual dengan auth yang benar per endpoint. (78 endpoint, 11 modul.)
- [x] Tabel digenerate/diekstrak dari router (bukan hardcoded manual) atau ada test yang menjaga sinkronisasi dengan router. (`scripts/gen_api_reference.py` + `test_api_reference_sync.py` — 4 test.)
- [x] Bagian auth: scopes + legacy key + contoh curl. (21 contoh, ≤2 per modul.)
- [x] Bagian webhook: WEBHOOK_EVENT_MAP + signature header. (`webhookEvents.ts` + sinkron di test.)
- [x] Commit + suite hijau. (pytest 442, vitest 100, tsc + build bersih.)
