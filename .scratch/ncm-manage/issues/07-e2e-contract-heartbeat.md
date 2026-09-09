# 07: Kontrak end-to-end + heartbeat/lastSeen + runbook

**What to build:**
Pengujian kontrak antar-repo di seam HTTP nyata (NCM test-server ↔ klien DG, bukan mock ganda), heartbeat berkala mengisi `lastSeenAt` untuk banner offline, dan runbook setup per site (prasyarat VPN, registrasi koneksi, konfigurasi webhook, alur operasional harian). Skenario demo penuh: tambah switch → trigger backup → drift muncul → review → incident terbentuk → approve → incident auto-resolve.

**Blocked by:** 5: DG halaman /admin/ncm; 6: DG ingest route + incident mapping.

**Status:** ready-for-agent

- [ ] Test kontrak HTTP nyata NCM↔DG hijau (client fetch melawan NCM test-server).
- [ ] Heartbeat worker mengisi `lastSeenAt` saat NCM terjangkau; banner akurat.
- [ ] Runbook per site tersimpan di docs (VPN, registrasi koneksi, webhook, operasional).
- [ ] Skenario demo penuh lulus: tambah switch → backup → drift → approve → incident resolve.