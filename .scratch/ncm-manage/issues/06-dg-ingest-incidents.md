# 06: DG ingest route + incident mapping

**What to build:**
Route `POST /api/ncm/ingest` di DataGuard menerima event NCM (auth HMAC per-site, rate-limit, validasi zod), memetakan event → incident (High: backup_failed/device_offline; Medium: drift), dedupe by NCM event ID, auto-resolve saat `backup_ok`/review approved, dan mengirim notifikasi Telegram per-site lewat jalur notifikasi yang sudah ada. Event untuk switch yang belum dipetakan ke device DG memakai device fallback per site (incidents.deviceId NOT NULL).

**Blocked by:** 3: NCM event webhook + HMAC dispatcher; 4: DG ncmSettings + lib/ncm.ts.

**Status:** done — `604f7d0` (route + lib/ncm-ingest.ts + 22 test)

- [x] HMAC salah/kurang → 401; valid → 200. Per-site secret dicocokkan ke semua ncm_settings (site count kecil).
- [x] Rate-limit aktif (60 req/menit/IP via lib/rate-limit); payload divalidasi zod (ncmIngestSchema).
- [x] Dedupe: marker `ncm_event_id:<key>` di description incident; event sama = no-op (test "dedupes by marker").
- [x] Mapping severity benar (backup_failed/device_offline → High, drift → Medium); auto-resolve saat backup_ok / review_decided approved.
- [x] Device tak dikenal → fallback device pertama site (503 bila site tanpa device); Telegram per-site fire-and-forget (siteTelegramChatIds).
