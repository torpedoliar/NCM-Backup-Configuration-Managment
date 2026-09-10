/**
 * Webhook event map — mirror of app_v4/service/events.py WEBHOOK_EVENT_MAP.
 * (Internal event name -> webhook event name(s) terverifikasi oleh
 * test_webhook_dispatcher tests. Menambahkan endpoint sinkron di sini tidak
 * wajib, tapi nilai yang salah membuat dokumentasi menyesatkan, jadi jaga
 * secara manual bila WEBHOOK_EVENT_MAP backend berubah.)
 */
export const WEBHOOK_EVENT_MAP: Record<string, string[]> = {
  backup_failed: ['backup_failed'],
  backup_completed: ['backup_ok'],
  config_drift: ['drift', 'review_opened'],
  review_opened: ['review_opened'],
  review_decided: ['review_decided'],
  device_offline: ['device_offline'],
};
