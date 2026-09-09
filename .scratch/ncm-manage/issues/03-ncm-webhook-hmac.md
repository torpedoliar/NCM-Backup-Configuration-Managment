# 03: NCM event webhook + HMAC dispatcher

**What to build:**
Event NCM (`backup_failed`, `backup_ok`, `drift`, `review_opened`, `review_decided`, `device_offline`) terkirim ke `webhook_url` yang dikonfigurasi, ditandatangani HMAC-SHA256 dengan `webhook_secret`. `webhook_secret` bisa diset via system API (PATCH model system). Notifier webhook dead-code dihidupkan lewat dispatcher EventHub. Tanpa secret/URL terisi = no-op aman (tidak crash, tidak retry tak berujung).

**Blocked by:** 1: NCM scoped API keys + combined auth.

**Status:** ready-for-agent

- [ ] Dispatcher mempublikasikan 6 jenis event ke Notifier.webhook (payload JSON, signature HMAC-SHA256 di header).
- [ ] Test: event → payload + HMAC terverifikasi dengan secret yang sama.
- [ ] `webhook_secret` dapat diset/diubah via system API.
- [ ] Tanpa URL/secret: tidak ada attempt kirim, tidak ada error di log aplikasi.