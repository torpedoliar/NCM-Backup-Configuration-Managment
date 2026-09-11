# 04: DG ncmSettings + lib/ncm.ts + koneksi per site

**What to build:**
Superadmin DataGuard dapat mendaftarkan koneksi NCM per site (URL + admin API key) dari UI admin. Key disimpan terenkripsi AES-256-GCM. Ada tombol test-connection yang melakukan roundtrip ke NCM dan menampilkan status. Tabel `ncmSettings` per site meniru pola `networkDocSettings` (migrasi SQL berikutnya setelah 0056, hand-written drizzle/ + _journal.json). Klien terpusat `lib/ncm.ts` (resolve config per site + fetch dengan timeout 10s + wrapper per operasi mengikuti bentuk `fetchNetworkDoc`).

**Blocked by:** 1: NCM scoped API keys + combined auth.

**Status:** done — `d47fe0e` (base: ncm_settings + lib/ncm.ts + form superadmin) + `0e38e2d` (T14: form gabungan Network Docs + NCM + HMAC 1-klik, scoped-key guidance)

- [x] Migrasi 0057 jalan (tabel ncmSettings per site). Ditambah 0058 (webhook_secret), 0059 (webhook_url), 0060 (heartbeat) di tiket 07–09.
- [x] Key at-rest terenkripsi AES-256-GCM (lib/crypto.ts decryptIfEncrypted; tidak ada plaintext di DB).
- [x] Form settings superadmin + test-connection hijau ke NCM sungguhan. Kini form gabungan per site (URL + key dipakai NCM management sekaligus Network Docs sync).
- [x] `lib/ncm.ts` dengan timeout 10s, envelope error, dan operasi: switches/backups/reviews/jobs/baselines read + write wrappers (createNcmSwitch, updateNcmCredentials, setNcmWebhook, dsb). Vitest: lib/ncm.test.ts + actions/ncm-settings.test.ts.
