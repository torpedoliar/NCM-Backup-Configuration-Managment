# 06: DG ingest route + incident mapping

**What to build:**
Route `POST /api/ncm/ingest` di DataGuard menerima event NCM (auth HMAC per-site, rate-limit, validasi zod), memetakan event → incident (High: backup_failed/device_offline; Medium: drift), dedupe by NCM event ID, auto-resolve saat `backup_ok`/review approved, dan mengirim notifikasi Telegram per-site lewat jalur notifikasi yang sudah ada. Event untuk switch yang belum dipetakan ke device DG memakai device fallback per site (incidents.deviceId NOT NULL).

**Blocked by:** 3: NCM event webhook + HMAC dispatcher; 4: DG ncmSettings + lib/ncm.ts.

**Status:** ready-for-agent

- [ ] HMAC salah/kurang → 401; valid → 200.
- [ ] Rate-limit aktif; payload divalidasi zod.
- [ ] Dedupe: event ID sama tidak membuat incident kedua.
- [ ] Mapping severity benar; auto-resolve saat backup_ok/review approved.
- [ ] Device tak dikenal → fallback device per site (constraint NOT NULL terpenuhi); Telegram per-site terkirim.