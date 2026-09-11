/**
 * NCM REST API reference data — GENERATED from the live routers by
 * scripts/gen_api_reference.py. DO NOT hand-edit the endpoint list: the pytest
 * `test_api_reference_sync` diffs (method, path) here against create_app()'s
 * routes and fails on drift. Regenerate when the backend changes:
 *
 *   ./.venv/Scripts/python.exe scripts/gen_api_reference.py
 *
 * Auth labels are derived from the require_* dependency closures; the summary
 * is the route summary (function name). Friendly one-line descriptions for
 * the UI live in ENDPOINT_DESCRIPTIONS below (also covered by the sync test).
 */
import { WEBHOOK_EVENT_MAP } from './webhookEvents';

export type ApiRefEntry = {
  method: 'DELETE' | 'GET' | 'PATCH' | 'POST' | 'PUT';
  path: string;
  tag: string;
  auth: string;
  summary: string;
  description?: string;
};

export const KNOWN_SCOPES: Record<string, string> = {
  read: 'Baca semua data (switch, backup, review, job, doc) — tidak bisa menulis',
  'switches:write': 'Tambah/ubah/aktif/nonaktif/hapus switch',
  'credentials:write': 'Tambah/ubah/hapus kredensial perangkat',
  'schedules:write': 'Kelola jadwal backup & jalankan job sekarang',
  'baselines:write': 'Buat/refresh/hapus golden baseline',
  'backup:write': 'Picu backup on-demand per switch',
  'reviews:write': 'Setujui/tolak review drift (status)',
  'system:write': 'Ubah konfigurasi notifikasi (termasuk webhook)',
};

/** Legacy key: dibuat tanpa scope (kolom NULL). Masih berlaku hanya untuk
 * integrasi yang belum dimigrasi — lihat catatan migrasi di bagian Auth. */
export const LEGACY_KEY_NOTE =
  'Key lama (tanpa scope) ditolak 403 di semua endpoint, termasuk /network-doc. ' +
  'Buat key baru dengan scope minimal di tab API lalu revoke key lama.';

export const WEBHOOK_SIGNATURE =
  'Webhook terverifikasi HMAC-SHA256: header X-NCM-Signature: sha256=<hex> ' +
  'dihitung atas body persis seperti yang dikirim (JSON compact). Verifikasi ' +
  'dengan webhook secret yang dikonfigurasi di NCM (Settings › Notifications).';

export const API_REF: ApiRefEntry[] = [
  { method: 'DELETE', path: '/api/v1/api-keys/{key_id}', tag: 'api-keys', auth: 'JWT (admin)', summary: 'delete_api_key' },
  { method: 'DELETE', path: '/api/v1/backups/{backup_id}', tag: 'backups', auth: 'JWT (admin)', summary: 'delete_backup' },
  { method: 'DELETE', path: '/api/v1/baselines/{baseline_id}', tag: 'config-reviews', auth: 'JWT admin or key baselines:write', summary: 'delete_baseline' },
  { method: 'DELETE', path: '/api/v1/credentials/{cred_id}', tag: 'credentials', auth: 'JWT admin or key credentials:write', summary: 'delete_credential' },
  { method: 'DELETE', path: '/api/v1/jobs/{job_id}', tag: 'jobs', auth: 'JWT admin/operator or key schedules:write', summary: 'delete_job' },
  { method: 'DELETE', path: '/api/v1/switches/{switch_id}', tag: 'switches', auth: 'JWT admin or key switches:write', summary: 'delete_switch' },
  { method: 'DELETE', path: '/api/v1/users/{user_id}', tag: 'users', auth: 'JWT (admin)', summary: 'delete_user' },
  { method: 'GET', path: '/api/v1/api-keys', tag: 'api-keys', auth: 'JWT (admin)', summary: 'list_api_keys' },
  { method: 'GET', path: '/api/v1/audit', tag: 'audit', auth: 'JWT (admin)', summary: 'list_audit' },
  { method: 'GET', path: '/api/v1/auth/me', tag: 'auth', auth: 'JWT (any role)', summary: 'me' },
  { method: 'GET', path: '/api/v1/backups', tag: 'backups', auth: 'JWT-or-key (scope: read)', summary: 'list_backups' },
  { method: 'GET', path: '/api/v1/backups/diff', tag: 'backups', auth: 'JWT-or-key (scope: read)', summary: 'diff_backups' },
  { method: 'GET', path: '/api/v1/backups/diff/side-by-side', tag: 'backups', auth: 'JWT-or-key (scope: read)', summary: 'diff_backups_side_by_side' },
  { method: 'GET', path: '/api/v1/backups/latest-per-switch', tag: 'backups', auth: 'JWT-or-key (scope: read)', summary: 'latest_backup_per_switch' },
  { method: 'GET', path: '/api/v1/backups/report', tag: 'backups', auth: 'JWT-or-key (scope: read)', summary: 'export_backups_report' },
  { method: 'GET', path: '/api/v1/backups/{backup_id}', tag: 'backups', auth: 'JWT-or-key (scope: read)', summary: 'get_backup' },
  { method: 'GET', path: '/api/v1/backups/{backup_id}/content', tag: 'backups', auth: 'JWT-or-key (scope: read)', summary: 'get_backup_content' },
  { method: 'GET', path: '/api/v1/backups/{backup_id}/decode', tag: 'backups', auth: 'JWT-or-key (scope: read)', summary: 'decode_backup' },
  { method: 'GET', path: '/api/v1/backups/{backup_id}/diff', tag: 'backups', auth: 'JWT-or-key (scope: read)', summary: 'get_backup_diff' },
  { method: 'GET', path: '/api/v1/baselines', tag: 'config-reviews', auth: 'JWT-or-key (scope: read)', summary: 'list_baselines' },
  { method: 'GET', path: '/api/v1/credentials', tag: 'credentials', auth: 'JWT (admin/operator)', summary: 'list_credentials' },
  { method: 'GET', path: '/api/v1/jobs', tag: 'jobs', auth: 'JWT-or-key (scope: read)', summary: 'list_jobs' },
  { method: 'GET', path: '/api/v1/network-doc', tag: 'network-doc', auth: 'JWT-or-key (scope: read)', summary: 'list_network_doc' },
  { method: 'GET', path: '/api/v1/network-doc/{switch_id}', tag: 'network-doc', auth: 'JWT-or-key (scope: read)', summary: 'get_network_doc' },
  { method: 'GET', path: '/api/v1/reviews', tag: 'config-reviews', auth: 'JWT-or-key (scope: read)', summary: 'list_reviews' },
  { method: 'GET', path: '/api/v1/reviews/compliance', tag: 'config-reviews', auth: 'JWT-or-key (scope: read)', summary: 'reviews_compliance' },
  { method: 'GET', path: '/api/v1/reviews/compliance/report', tag: 'config-reviews', auth: 'JWT-or-key (scope: read)', summary: 'compliance_report' },
  { method: 'GET', path: '/api/v1/reviews/{review_id}/diff', tag: 'config-reviews', auth: 'JWT-or-key (scope: read)', summary: 'review_diff' },
  { method: 'GET', path: '/api/v1/reviews/{review_id}/notes', tag: 'config-reviews', auth: 'JWT-or-key (scope: read)', summary: 'list_review_notes' },
  { method: 'GET', path: '/api/v1/reviews/{review_id}/rollback', tag: 'config-reviews', auth: 'JWT-or-key (scope: read)', summary: 'review_rollback_script' },
  { method: 'GET', path: '/api/v1/switches', tag: 'switches', auth: 'JWT-or-key (scope: read)', summary: 'list_switches' },
  { method: 'GET', path: '/api/v1/switches/{switch_id}', tag: 'switches', auth: 'JWT-or-key (scope: read)', summary: 'get_switch' },
  { method: 'GET', path: '/api/v1/system/auth-settings', tag: 'system', auth: 'JWT (admin)', summary: 'get_auth_settings' },
  { method: 'GET', path: '/api/v1/system/autostart', tag: 'system', auth: 'JWT (admin/operator/viewer)', summary: 'get_autostart' },
  { method: 'GET', path: '/api/v1/system/backup-location', tag: 'system', auth: 'JWT (admin/operator/viewer)', summary: 'get_backup_location' },
  { method: 'GET', path: '/api/v1/system/logs', tag: 'system', auth: 'JWT (admin)', summary: 'get_logs' },
  { method: 'GET', path: '/api/v1/system/metrics', tag: 'system', auth: 'JWT (admin/operator/viewer)', summary: 'metrics' },
  { method: 'GET', path: '/api/v1/system/notify-settings', tag: 'system', auth: 'JWT (admin/operator)', summary: 'get_notify_settings' },
  { method: 'GET', path: '/api/v1/system/retention', tag: 'system', auth: 'JWT (admin/operator/viewer)', summary: 'get_retention' },
  { method: 'GET', path: '/api/v1/system/scheduler-status', tag: 'system', auth: 'JWT (admin/operator/viewer)', summary: 'scheduler_status' },
  { method: 'GET', path: '/api/v1/system/status', tag: 'system', auth: 'JWT (admin/operator/viewer)', summary: 'status' },
  { method: 'GET', path: '/api/v1/system/time-settings', tag: 'system', auth: 'JWT (admin/operator/viewer)', summary: 'get_time_settings' },
  { method: 'GET', path: '/api/v1/users', tag: 'users', auth: 'JWT (admin)', summary: 'list_users' },
  { method: 'PATCH', path: '/api/v1/api-keys/{key_id}', tag: 'api-keys', auth: 'JWT (admin)', summary: 'update_api_key' },
  { method: 'PATCH', path: '/api/v1/credentials/{cred_id}', tag: 'credentials', auth: 'JWT admin or key credentials:write', summary: 'update_credential' },
  { method: 'PATCH', path: '/api/v1/jobs/{job_id}', tag: 'jobs', auth: 'JWT admin/operator or key schedules:write', summary: 'update_job' },
  { method: 'PATCH', path: '/api/v1/switches/{switch_id}', tag: 'switches', auth: 'JWT admin/operator or key switches:write', summary: 'update_switch' },
  { method: 'PATCH', path: '/api/v1/system/auth-settings', tag: 'system', auth: 'JWT (admin)', summary: 'patch_auth_settings' },
  { method: 'PATCH', path: '/api/v1/system/backup-location', tag: 'system', auth: 'JWT (admin)', summary: 'patch_backup_location' },
  { method: 'PATCH', path: '/api/v1/system/notify-settings', tag: 'system', auth: 'JWT admin or key system:write', summary: 'patch_notify_settings' },
  { method: 'PATCH', path: '/api/v1/system/retention', tag: 'system', auth: 'JWT (admin)', summary: 'patch_retention' },
  { method: 'PATCH', path: '/api/v1/system/time-settings', tag: 'system', auth: 'JWT (admin)', summary: 'patch_time_settings' },
  { method: 'PATCH', path: '/api/v1/users/{user_id}', tag: 'users', auth: 'JWT (admin)', summary: 'update_user' },
  { method: 'POST', path: '/api/v1/api-keys', tag: 'api-keys', auth: 'JWT (admin)', summary: 'create_api_key' },
  { method: 'POST', path: '/api/v1/auth/login', tag: 'auth', auth: 'public (no credentials)', summary: 'login' },
  { method: 'POST', path: '/api/v1/auth/logout', tag: 'auth', auth: 'public (no credentials)', summary: 'logout' },
  { method: 'POST', path: '/api/v1/auth/refresh', tag: 'auth', auth: 'public (no credentials)', summary: 'refresh' },
  { method: 'POST', path: '/api/v1/baselines', tag: 'config-reviews', auth: 'JWT admin or key baselines:write', summary: 'create_baseline' },
  { method: 'POST', path: '/api/v1/baselines/{baseline_id}/refresh', tag: 'config-reviews', auth: 'JWT admin or key baselines:write', summary: 'refresh_baseline' },
  { method: 'POST', path: '/api/v1/credentials', tag: 'credentials', auth: 'JWT admin or key credentials:write', summary: 'create_credential' },
  { method: 'POST', path: '/api/v1/jobs', tag: 'jobs', auth: 'JWT admin/operator or key schedules:write', summary: 'create_job' },
  { method: 'POST', path: '/api/v1/jobs/{job_id}/run', tag: 'jobs', auth: 'JWT admin/operator or key schedules:write', summary: 'run_job_now' },
  { method: 'POST', path: '/api/v1/reviews/run-cycle', tag: 'config-reviews', auth: 'JWT (admin/operator)', summary: 'run_fleet_cycle_review' },
  { method: 'POST', path: '/api/v1/reviews/{review_id}/notes', tag: 'config-reviews', auth: 'JWT (admin/operator)', summary: 'add_review_note' },
  { method: 'POST', path: '/api/v1/reviews/{review_id}/promote-baseline', tag: 'config-reviews', auth: 'JWT (admin/operator)', summary: 'promote_review_to_baseline' },
  { method: 'POST', path: '/api/v1/reviews/{review_id}/start', tag: 'config-reviews', auth: 'JWT (admin/operator)', summary: 'start_review' },
  { method: 'POST', path: '/api/v1/reviews/{review_id}/status', tag: 'config-reviews', auth: 'JWT admin/operator or key reviews:write', summary: 'update_review_status' },
  { method: 'POST', path: '/api/v1/switches', tag: 'switches', auth: 'JWT admin/operator or key switches:write', summary: 'create_switch' },
  { method: 'POST', path: '/api/v1/switches/{switch_id}/activate', tag: 'switches', auth: 'JWT admin/operator or key switches:write', summary: 'activate_switch' },
  { method: 'POST', path: '/api/v1/switches/{switch_id}/backup', tag: 'backups', auth: 'JWT admin/operator or key backup:write', summary: 'trigger_backup_spec_alias' },
  { method: 'POST', path: '/api/v1/switches/{switch_id}/backups', tag: 'backups', auth: 'JWT admin/operator or key backup:write', summary: 'trigger_backup' },
  { method: 'POST', path: '/api/v1/switches/{switch_id}/deactivate', tag: 'switches', auth: 'JWT admin/operator or key switches:write', summary: 'deactivate_switch' },
  { method: 'POST', path: '/api/v1/system/notify/test', tag: 'system', auth: 'JWT (admin)', summary: 'test_notify' },
  { method: 'POST', path: '/api/v1/system/notify/test-reminder', tag: 'system', auth: 'JWT (admin)', summary: 'test_notify_reminder' },
  { method: 'POST', path: '/api/v1/system/retention/run', tag: 'system', auth: 'JWT (admin)', summary: 'run_retention_now' },
  { method: 'POST', path: '/api/v1/users', tag: 'users', auth: 'JWT (admin)', summary: 'create_user' },
  { method: 'POST', path: '/api/v1/users/{user_id}/password', tag: 'users', auth: 'JWT (admin)', summary: 'reset_password' },
  { method: 'POST', path: '/api/v1/users/{user_id}/unlock', tag: 'users', auth: 'JWT (admin)', summary: 'unlock_user' },
  { method: 'PUT', path: '/api/v1/system/autostart', tag: 'system', auth: 'JWT (admin)', summary: 'put_autostart' },
];

/** Friendly Indonesian descriptions keyed by `${method} ${path}`. Kept in sync
 * with the generated list by test_api_reference_sync (every entry must have one,
 * none may be orphaned). */
export const ENDPOINT_DESCRIPTIONS: Record<string, string> = {
  'DELETE /api/v1/api-keys/{key_id}': 'Hapus permanen key API',
  'DELETE /api/v1/backups/{backup_id}': 'Hapus file backup',
  'DELETE /api/v1/baselines/{baseline_id}': 'Hapus golden baseline',
  'DELETE /api/v1/credentials/{cred_id}': 'Hapus kredensial perangkat',
  'DELETE /api/v1/jobs/{job_id}': 'Hapus jadwal backup',
  'DELETE /api/v1/switches/{switch_id}': 'Hapus switch (harus nonaktif dulu)',
  'DELETE /api/v1/users/{user_id}': 'Hapus user',
  'GET /api/v1/api-keys': 'Daftar API key (hash + prefix, tanpa plaintext)',
  'GET /api/v1/audit': 'Jejak audit (login, perubahan, keputusan review)',
  'GET /api/v1/auth/me': 'Profil user yang sedang login',
  'GET /api/v1/backups': 'Daftar backup (filter switch/status/waktu)',
  'GET /api/v1/backups/diff': 'Diff dua backup (unified)',
  'GET /api/v1/backups/diff/side-by-side': 'Diff dua backup (berdampingan)',
  'GET /api/v1/backups/latest-per-switch': 'Backup terakhir tiap switch',
  'GET /api/v1/backups/report': 'Laporan backup (format csv/pdf/xlsx)',
  'GET /api/v1/backups/{backup_id}': 'Metadata satu backup',
  'GET /api/v1/backups/{backup_id}/content': 'Isi mentah file backup',
  'GET /api/v1/backups/{backup_id}/decode': 'Backup ter-decode (VLAN/port terstruktur)',
  'GET /api/v1/backups/{backup_id}/diff': 'Diff backup vs backup pembandingnya',
  'GET /api/v1/baselines': 'Daftar golden baseline',
  'GET /api/v1/credentials': 'Daftar kredensial (username saja, tanpa password)',
  'GET /api/v1/jobs': 'Daftar jadwal backup',
  'GET /api/v1/network-doc': 'Dokumentasi jaringan terstruktur semua switch aktif',
  'GET /api/v1/network-doc/{switch_id}': 'Dokumentasi jaringan satu switch',
  'GET /api/v1/reviews': 'Antrian review drift (filter status/switch)',
  'GET /api/v1/reviews/compliance': 'Ringkasan kepatuhan per switch',
  'GET /api/v1/reviews/compliance/report': 'Laporan kepatuhan (csv/pdf/xlsx)',
  'GET /api/v1/reviews/{review_id}/diff': 'Diff mentah review (text/plain)',
  'GET /api/v1/reviews/{review_id}/notes': 'Catatan review',
  'GET /api/v1/reviews/{review_id}/rollback': 'Skrip rollback config sebelumnya',
  'GET /api/v1/switches': 'Daftar switch aktif',
  'GET /api/v1/switches/{switch_id}': 'Detail satu switch',
  'GET /api/v1/system/auth-settings': 'Kebijakan password & lockout',
  'GET /api/v1/system/autostart': 'Status auto-start service',
  'GET /api/v1/system/backup-location': 'Folder penyimpanan backup',
  'GET /api/v1/system/logs': 'Log layanan (tail)',
  'GET /api/v1/system/metrics': 'Metrik ringkas untuk dashboard',
  'GET /api/v1/system/notify-settings': 'Konfigurasi notifikasi (email/telegram/webhook)',
  'GET /api/v1/system/retention': 'Kebijakan retensi backup',
  'GET /api/v1/system/scheduler-status': 'Status scheduler job',
  'GET /api/v1/system/status': 'Status umum layanan',
  'GET /api/v1/system/time-settings': 'Zona waktu & NTP',
  'GET /api/v1/users': 'Daftar user',
  'PATCH /api/v1/api-keys/{key_id}': 'Ubah nama atau scope API key (admin JWT)',
  'PATCH /api/v1/credentials/{cred_id}': 'Ubah kredensial (password dienkripsi)',
  'PATCH /api/v1/jobs/{job_id}': 'Ubah jadwal backup',
  'PATCH /api/v1/switches/{switch_id}': 'Ubah data switch (nama/IP/protokol/port)',
  'PATCH /api/v1/system/auth-settings': 'Ubah kebijakan password & lockout',
  'PATCH /api/v1/system/backup-location': 'Pindahkan folder backup',
  'PATCH /api/v1/system/notify-settings': 'Ubah notifikasi & webhook (admin JWT atau key system:write)',
  'PATCH /api/v1/system/retention': 'Ubah kebijakan retensi',
  'PATCH /api/v1/system/time-settings': 'Ubah zona waktu & NTP',
  'PATCH /api/v1/users/{user_id}': 'Ubah peran/reset status user',
  'POST /api/v1/api-keys': 'Buat API key — plaintext hanya tampil sekali',
  'POST /api/v1/auth/login': 'Login, dapat access + refresh token',
  'POST /api/v1/auth/logout': 'Cabut refresh token',
  'POST /api/v1/auth/refresh': 'Perbarui access token',
  'POST /api/v1/baselines': 'Buat baseline dari backup terakhir switch',
  'POST /api/v1/baselines/{baseline_id}/refresh': 'Segarkan baseline ke backup termutakhir',
  'POST /api/v1/credentials': 'Tambah kredensial perangkat',
  'POST /api/v1/jobs': 'Buat jadwal backup',
  'POST /api/v1/jobs/{job_id}/run': 'Jalankan jadwal sekarang',
  'POST /api/v1/reviews/run-cycle': 'Picu siklus review drift satu fleet',
  'POST /api/v1/reviews/{review_id}/notes': 'Tambah catatan review',
  'POST /api/v1/reviews/{review_id}/promote-baseline': 'Jadikan hasil review baseline baru',
  'POST /api/v1/reviews/{review_id}/start': 'Mulai pengerjaan review',
  'POST /api/v1/reviews/{review_id}/status': 'Setujui/tolak review drift',
  'POST /api/v1/switches': 'Tambah switch',
  'POST /api/v1/switches/{switch_id}/activate': 'Aktifkan kembali switch',
  'POST /api/v1/switches/{switch_id}/backup': 'Picu backup on-demand (alias)',
  'POST /api/v1/switches/{switch_id}/backups': 'Picu backup on-demand',
  'POST /api/v1/switches/{switch_id}/deactivate': 'Nonaktifkan switch (syarat hapus)',
  'POST /api/v1/system/notify/test': 'Uji kirim notifikasi',
  'POST /api/v1/system/notify/test-reminder': 'Uji kirim pengingat backup',
  'POST /api/v1/system/retention/run': 'Jalankan pembersihan retensi sekarang',
  'POST /api/v1/users': 'Tambah user',
  'POST /api/v1/users/{user_id}/password': 'Reset password user',
  'POST /api/v1/users/{user_id}/unlock': 'Buka kunci user yang ter-lockout',
  'PUT /api/v1/system/autostart': 'Aktif/nonaktifkan auto-start service',
};

/** Curl examples per module (maks 2 per modul), pola dari probe DG. */
export const CURL_EXAMPLES: { tag: string; title: string; code: string }[] = [
  {
    tag: 'auth',
    title: 'Dapatkan token JWT',
    code: `curl -X POST http://localhost:8443/api/v1/auth/login \\\n  -H "Content-Type: application/json" \\\n  -d '{"username":"admin","password":"***"}'`,
  },
  {
    tag: 'auth',
    title: 'Profil user login',
    code: `curl -H "Authorization: Bearer <access-token>" \\\n  http://localhost:8443/api/v1/auth/me`,
  },
  {
    tag: 'switches',
    title: 'Daftar switch (JWT atau key scope read)',
    code: `curl -H "X-API-Key: <key>" \\\n  http://localhost:8443/api/v1/switches`,
  },
  {
    tag: 'switches',
    title: 'Tambah switch (admin/operator JWT atau key switches:write)',
    code: `curl -X POST http://localhost:8443/api/v1/switches \\\n  -H "X-API-Key: <key-dengan-scope-switches:write>" \\\n  -H "Content-Type: application/json" \\\n  -d '{"name":"SW-CORE-01","ip":"192.168.10.1","protocol":"ssh","port":22,"credential_id":1}'`,
  },
  {
    tag: 'backups',
    title: 'Daftar backup',
    code: `curl -H "X-API-Key: <key>" "http://localhost:8443/api/v1/backups?switch_id=1&limit=20"`,
  },
  {
    tag: 'backups',
    title: 'Picu backup on-demand',
    code: `curl -X POST http://localhost:8443/api/v1/switches/1/backups \\\n  -H "X-API-Key: <key-dengan-scope-backup:write>"`,
  },
  {
    tag: 'credentials',
    title: 'Daftar kredensial',
    code: `curl -H "Authorization: Bearer <access-token>" \\\n  http://localhost:8443/api/v1/credentials`,
  },
  {
    tag: 'credentials',
    title: 'Tambah kredensial (password langsung terenkripsi)',
    code: `curl -X POST http://localhost:8443/api/v1/credentials \\\n  -H "X-API-Key: <key-dengan-scope-credentials:write>" \\\n  -H "Content-Type: application/json" \\\n  -d '{"name":"lab","username":"rotor","password":"***"}'`,
  },
  {
    tag: 'jobs',
    title: 'Daftar jadwal',
    code: `curl -H "X-API-Key: <key>" \\\n  http://localhost:8443/api/v1/jobs`,
  },
  {
    tag: 'jobs',
    title: 'Jalankan jadwal sekarang',
    code: `curl -X POST http://localhost:8443/api/v1/jobs/3/run \\\n  -H "X-API-Key: <key-dengan-scope-schedules:write>"`,
  },
  {
    tag: 'config-reviews',
    title: 'Antrian review drift',
    code: `curl -H "X-API-Key: <key>" \\\n  "http://localhost:8443/api/v1/reviews?status=pending"`,
  },
  {
    tag: 'config-reviews',
    title: 'Setujui review (operator/admin JWT atau key reviews:write)',
    code: `curl -X POST http://localhost:8443/api/v1/reviews/12/status \\\n  -H "Authorization: Bearer <access-token>" \\\n  -H "Content-Type: application/json" \\\n  -d '{"decision":"approved","note":"perubahan disetujui tim jaringan"}'`,
  },
  {
    tag: 'network-doc',
    title: 'Dokumentasi jaringan semua switch aktif (dipakai DataGuard)',
    code: `curl -H "X-API-Key: <key-dengan-scope-read>" \\\n  http://localhost:8443/api/v1/network-doc`,
  },
  {
    tag: 'network-doc',
    title: 'Dokumentasi satu switch',
    code: `curl -H "X-API-Key: <key>" \\\n  http://localhost:8443/api/v1/network-doc/3`,
  },
  {
    tag: 'system',
    title: 'Status layanan',
    code: `curl -H "Authorization: Bearer <access-token>" \\\n  http://localhost:8443/api/v1/system/status`,
  },
  {
    tag: 'system',
    title: 'Uji konfigurasi webhook/notifikasi',
    code: `curl -X POST http://localhost:8443/api/v1/system/notify/test \\\n  -H "Authorization: Bearer <access-token-admin>"`,
  },
  {
    tag: 'api-keys',
    title: 'Buat API key dengan scope',
    code: `curl -X POST http://localhost:8443/api/v1/api-keys \\\n  -H "Authorization: Bearer <access-token-admin>" \\\n  -H "Content-Type: application/json" \\\n  -d '{"name":"dataguard","scopes":["read","switches:write","backup:write","reviews:write","schedules:write"]}'`,
  },
  {
    tag: 'api-keys',
    title: 'Daftar API key',
    code: `curl -H "Authorization: Bearer <access-token-admin>" \\\n  http://localhost:8443/api/v1/api-keys`,
  },
  {
    tag: 'users',
    title: 'Daftar user (admin)',
    code: `curl -H "Authorization: Bearer <access-token-admin>" \\\n  http://localhost:8443/api/v1/users`,
  },
  {
    tag: 'users',
    title: 'Tambah user operator',
    code: `curl -X POST http://localhost:8443/api/v1/users \\\n  -H "Authorization: Bearer <access-token-admin>" \\\n  -H "Content-Type: application/json" \\\n  -d '{"username":"tekisi1","password":"***","role":"operator"}'`,
  },
  {
    tag: 'audit',
    title: 'Jejak audit (admin)',
    code: `curl -H "Authorization: Bearer <access-token-admin>" \\\n  "http://localhost:8443/api/v1/audit?limit=50"`,
  },
];

export { WEBHOOK_EVENT_MAP };
