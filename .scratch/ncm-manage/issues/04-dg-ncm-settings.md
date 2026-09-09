# 04: DG ncmSettings + lib/ncm.ts + koneksi per site

**What to build:**
Superadmin DataGuard dapat mendaftarkan koneksi NCM per site (URL + admin API key) dari UI admin. Key disimpan terenkripsi AES-256-GCM. Ada tombol test-connection yang melakukan roundtrip ke NCM dan menampilkan status. Tabel `ncmSettings` per site meniru pola `networkDocSettings` (migrasi SQL berikutnya setelah 0056, hand-written drizzle/ + _journal.json). Klien terpusat `lib/ncm.ts` (resolve config per site + fetch dengan timeout 10s + wrapper per operasi mengikuti bentuk `fetchNetworkDoc`).

**Blocked by:** 1: NCM scoped API keys + combined auth.

**Status:** ready-for-agent

- [ ] Migrasi 0057 jalan (tabel ncmSettings per site).
- [ ] Key at-rest terenkripsi AES-256-GCM (tidak ada plaintext di DB).
- [ ] Form settings superadmin + test-connection hijau ke NCM sungguhan.
- [ ] `lib/ncm.ts` dengan timeout, envelope error, dan minimal operasi: health/read switches. Vitest untuk error mapping.