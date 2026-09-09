# 07: Kontrak end-to-end + heartbeat/lastSeen + runbook

**What to build:**
Pengujian kontrak antar-repo di seam HTTP nyata (NCM test-server ↔ klien DG, bukan mock ganda), heartbeat berkala mengisi `lastSeenAt` untuk banner offline, dan runbook setup per site (prasyarat VPN, registrasi koneksi, konfigurasi webhook, alur operasional harian). Skenario demo penuh: tambah switch → trigger backup → drift muncul → review → incident terbentuk → approve → incident auto-resolve.

**Blocked by:** 5: DG halaman /admin/ncm; 6: DG ingest route + incident mapping.

**Status:** done (NCM 6923c73; DG probe+runbook 6a192a2)

- [x] Test kontrak HTTP nyata NCM↔DG hijau: `app_v4/tests/e2e_server.py` (uvicorn live server) ↔ DG `scripts/ncm-contract-probe.ts` — path, auth (X-API-Key + scopes), CRUD switch/credential, backup, baseline, drift→pending review, approve via `reviews:write`, rollback script. Lulus live, bukan mock. (HMAC ingest sudah diuji di tiket 06: 22 test.)
- [x] Heartbeat: test-connection DG menulis `lastSeenAt` (`touchNcmLastSeen`); banner offline membacanya.
- [x] Runbook: `docs/runbook-ncm-dg.md` di repo DG (VPN, registrasi koneksi, webhook, operasional, troubleshooting).
- [x] Skenario demo penuh lulus: bootstrap credential → switch → rotasi kredensial → backup → baseline → drift backup → pending review → approve → rollback.
