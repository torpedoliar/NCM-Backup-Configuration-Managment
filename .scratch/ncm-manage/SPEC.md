# Spec: DataGuard Full Management atas NCM per Site

> Feature slug: `ncm-manage` — sumber: sesi grilling Q1-Q9 + analisis kode kedua repo (2026-09-09).

## Problem Statement
Tim mengelola banyak site, masing-masing punya NCM desktop (backup config switch + drift review) yang hari ini hanya bisa dioperasikan lokal per mesin. DataGuard sentral sudah menarik data VLAN/port read-only via network-doc sync, tapi tidak bisa memicu backup, me-review drift, apalagi mengelola switch/kredensial/jadwal — teknisi harus remote ke tiap mesin NCM.

## Solution
DataGuard menjadi panel manajemen sentral untuk seluruh NCM site: CRUD switch, update kredensial (pass-through aman), kelola jadwal & baseline, trigger backup, approve/reject review drift, dan menerima event NCM sebagai incident — semua di atas VPN antar-site yang sudah ada, dengan webhook+HMAC bila site bisa keluar dan polling sebagai fallback.

## User Stories
1. Sebagai superadmin, saya ingin mendaftarkan koneksi NCM per site (URL + API key) agar DataGuard bisa berbicara ke tiap NCM.
2. Sebagai superadmin, saya ingin memutar API key NCM dari DataGuard agar key bocor bisa diganti tanpa akses mesin NCM.
3. Sebagai site admin, saya ingin melihat daftar switch NCM beserta status backup terakhir agar tahu kondisi fleet tanpa buka mesin NCM.
4. Sebagai site admin, saya ingin menambah switch baru dari DataGuard (IP, protokol, port, kredensial awal) agar provisioning terpusat.
5. Sebagai site admin, saya ingin mengedit switch (nama, IP, protokol, port) dari DataGuard agar perubahan tercatat di audit log.
6. Sebagai site admin, saya ingin menghapus/menonaktifkan switch dari DataGuard agar fleet bersih.
7. Sebagai site admin, saya ingin mengupdate password switch dari DataGuard agar rotasi kredensial bisa dilakukan sentral, tanpa password bisa dibaca balik oleh siapa pun.
8. Sebagai site admin, saya ingin memicu backup on-demand per switch agar tidak menunggu jadwal.
9. Sebagai site admin, saya ingin melihat jadwal backup dan mengubahnya agar sesuai window maintenance site.
10. Sebagai site admin, saya ingin membuat golden baseline dari backup terakhir agar drift detection punya acuan.
11. Sebagai site admin, saya ingin melihat antrian review drift (VLAN/port/hostname berubah + diff) agar perubahan config terkontrol.
12. Sebagai site admin, saya ingin approve/reject review dengan catatan agar keputusan tercatat dan audit-ready.
13. Sebagai site admin, saya ingin melihat banner jelas saat NCM site offline (terakhir terlihat kapan) dan tombol aksi disabled, agar tidak menembak perintah ke sistem mati.
14. Sebagai site admin, saya ingin kegagalan backup NCM otomatis menjadi incident High agar masuk SLA follow-up.
15. Sebagai site admin, saya ingin drift terdeteksi menjadi incident Medium agar tidak terlewat.
16. Sebagai site admin, saya ingin incident auto-resolve saat backup pulih/review disetujui agar antrian tetap bersih.
17. Sebagai auditor, saya ingin semua aksi manajemen NCM tercatat di audit log DataGuard (tanpa nilai password) agar memenuhi kebutuhan bukti.

## Implementation Decisions
- NCM auth: kolom `scopes` pada model API key (`read`, `backup:write`, `review:write`, `switches:write`, `credentials:write`, `schedules:write`, `baselines:write`); dependency auth gabungan JWT-atau-key di semua router terkait; key tanpa scope = perilaku lama (hanya network-doc).
- Kredensial pass-through: endpoint set/update kredensial menerima plaintext sekali jalan, NCM enkripsi-at-rest (DPAPI), tidak ada endpoint read-back; audit mencatat aksi tanpa nilai.
- Event push: hidupkan `Notifier.webhook()` via dispatcher EventHub untuk `backup_failed/backup_ok/drift/review_opened/review_decided/device_offline`; payload ditandatangani HMAC-SHA256 (`webhook_secret` di runtime settings + PATCH model system API).
- DG config: tabel `ncmSettings` per site (url, adminApiKey terenkripsi AES-256-GCM, `lastSeenAt` heartbeat), meniru pola `networkDocSettings`; migrasi lanjutan setelah 0056.
- DG client: `lib/ncm.ts` (resolve config + fetch 10s timeout + wrapper per operasi), actions mengikuti pola `requireActiveSiteAdminAction` + zod + audit + `revalidatePath`.
- DG ingest: route `POST /api/ncm/ingest` (auth HMAC per-site, rate-limit, zod), mapping device IP->nama, dedupe by NCM event ID, reuse jalur notifikasi Telegram per-site; fallback: site tanpa webhook mengandalkan polling status worker.
- DG UI: halaman `/admin/ncm` per site, 4 area (Switches, Backups & Schedules, Baselines & Reviews, Connection superadmin-only); status live (transient, tidak disync ke DB kecuali heartbeat).
- Transport: VPN antar-site yang sudah ada sebagai prasyarat tertulis; tanpa TLS di NCM pada tahap ini.

## Testing Decisions
- Test yang baik: perilaku eksternal di seam publik (HTTP contract NCM, Server Action DG), bukan detail implementasi.
- NCM: pytest untuk scopes/auth matrix (key tiap scope vs tiap endpoint), dispatcher webhook (event->payload+HMAC), regresi perilaku lama tanpa scope.
- DG: Vitest untuk `lib/ncm.ts` (timeout, envelope, error mapping), actions (guard + audit), ingest route (HMAC valid/invalid, dedupe, device tak dikenal); pola acuan test network-doc yang sudah ada.
- Kontrak antar-repo diuji di seam HTTP nyata (NCM test-server <-> client fetch), bukan mock ganda.

## Out of Scope
- TLS di NCM / terminasi sertifikat per site.
- Antrean perintah saat NCM offline (tampil offline + coba lagi, tanpa queue).
- Sync topologi VLAN/port dua arah penuh (tetap network-doc sync yang ada).
- Rotasi otomatis password switch; SSO antara DG dan NCM.
- i18n halaman baru (mengikuti preseden network-doc: string Indonesia hardcoded).

## Further Notes
- `incidents.deviceId` NOT NULL: event untuk switch yang belum dipetakan ke device DG butuh device fallback per site (keputusan implementasi, dicatat di tiket).
- Polling status + `lastSeenAt` memberi heartbeat gratis untuk banner offline.
- Ponytail: tanpa tabel sinkron baru untuk status fleet (transient, live-fetch); tanpa abstraksi client generik baru (ikuti bentuk `fetchNetworkDoc`).

## Prasyarat (external)
- VPN antar-site aktif dan DG sentral dapat menjangkau NCM tiap site (HTTP).
