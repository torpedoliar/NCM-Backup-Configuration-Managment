# Allied Telesis Backup Configuration Manager — Dokumentasi Pengguna

Versi: 3.1  
Platform: Windows 10/11 (64-bit)

---

## 1. Ringkasan
Aplikasi desktop untuk melakukan backup otomatis konfigurasi switch Allied Telesis. Menyediakan penjadwalan (scheduler), enkripsi kredensial, dashboard, histori, perbandingan konfigurasi (diff), dan layanan background (tanpa GUI) yang berjalan 24/7 melalui Windows Service atau Task Scheduler.

---

## 2. Fitur Utama
- Multi-protocol: SSH & Telnet
- Encrypted Credential Vault (Fernet AES, PBKDF2-HMAC-SHA256)
- Automated Scheduling (interval & jadwal harian/mingguan/bulanan)
- Manual backup on-demand
- Configuration Diff Viewer
- Retention Policy (default 365 hari)
- Windows Service (pywin32) & Fallback Task Scheduler
- Dashboard & Monitoring real-time
- Ekspor/Impor konfigurasi
- Logging rotasi (file log otomatis diputar)

---

## 3. Persyaratan Sistem
- Windows 10/11 64-bit
- Mode Production: EXE standalone (tidak perlu Python terpasang)
- Mode Source (opsional): Python 3.11+, paket pada `requirements.txt`
- Akses jaringan ke switch dan ke lokasi penyimpanan backup (bisa UNC share)

---

## 4. Struktur Folder Runtime (Production EXE)
Semua path menggunakan direktori dasar aplikasi (base_dir), yaitu folder tempat EXE berada.

- `<base_dir>/data/app.db` — Database SQLite
- `<base_dir>/data/master.key` — Salt + token validasi passphrase
- `<base_dir>/data/.gui_passphrase` — Auto-login GUI (opsional)
- `<base_dir>/data/.service_passphrase` — Passphrase untuk layanan background
- `<base_dir>/logs/app.log` — Log aplikasi (rotating)
- `<base_dir>/backups/` — Hasil file konfigurasi backup
- `<base_dir>/config/appsettings.yaml` — File konfigurasi aplikasi

Catatan: Pada first run (EXE), `appsettings.yaml` akan dicopy dari bundle ke `<base_dir>/config` jika belum ada.

---

## 5. Instalasi (Production EXE)
1. Salin file EXE ke folder tujuan (contoh: `C:\Program Files\AlliedTelesisBackup\`).
2. Jalankan EXE. UI akan terbuka.
3. Pertama kali, sistem akan meminta Master Passphrase (min. 8 karakter).
4. Opsional: aktifkan Auto-Login agar tidak diminta passphrase saat startup.

Tips: Untuk backup ke UNC, direkomendasikan folder EXE berada di disk lokal dan jalankan layanan sebagai user yang memiliki akses ke UNC.

---

## 6. Konfigurasi (appsettings.yaml)
Lokasi: `<base_dir>/config/appsettings.yaml`

Parameter penting:
- `backup.root_folder`: Folder root untuk menyimpan backup (boleh UNC)
- `backup.retention_days`: Lama penyimpanan default (mis. 365)
- `logging.level`: `INFO`/`DEBUG`/`WARNING`

Edit file ini saat aplikasi tidak berjalan. Simpan, lalu buka ulang aplikasi/layanan.

---

## 7. Penggunaan Dasar
1. Tambah Credential: tab Credentials → isi username/password/enable password → Simpan.
2. Tambah Switch: tab Inventory → isi name, IP, protocol (SSH/Telnet), port, pilih credential.
3. Manual Backup: tab Inventory/History → pilih switch → klik Backup.
4. Lihat History: tab History → pilih switch → lihat daftar backup → View/Export/Open Folder.
5. Lihat Diff: tab Diff → bandingkan dua versi konfigurasi.

---

## 8. Penjadwalan (Schedules)
- Buat jadwal di tab Schedules: pilih switch, tentukan interval atau waktu spesifik (jam/menit, harian/mingguan/bulanan).
- Scheduler akan mengeksekusi backup otomatis sesuai jadwal.
- Gunakan tombol "Run Now" untuk uji cepat.

---

## 9. Menjalankan di Latar Belakang (24/7)
Aplikasi mendukung dua opsi:

- Opsi A — Windows Service (pywin32):
  - Tab Settings → tombol Install/Uninstall Service.
  - Membutuhkan passphrase di `<base_dir>/data/.service_passphrase` (diset saat install).
  - Service berjalan via Service Control Manager (SCM).

- Opsi B — Task Scheduler (Fallback console mode):
  - Tab Settings → tombol Setup Auto-Start (jadwalkan `<exe> --service`).
  - Jika tidak diluncurkan via SCM, aplikasi otomatis fallback ke mode console background.
  - Direkomendasikan memilih akun user jika `backup.root_folder` adalah UNC.

Catatan:
- Log layanan: `<base_dir>/logs/app.log`.
- Anda dapat menutup GUI; layanan background tetap berjalan.
- Untuk stop/uninstall: gunakan tombol di tab Settings.

---

## 10. Retention (Pembersihan Otomatis)
- Retention Service berjalan harian (default 02:00) sesuai konfigurasi.
- Aturan default: simpan 365 hari, minimal 1 backup per switch.
- Service akan menghapus file backup lama dan mencatat di database.

---

## 11. Ekspor/Impor Konfigurasi
- Ekspor: simpan konfigurasi switch dan jadwal ke file.
- Impor: muat kembali konfigurasi dari file ekspor.
- Catatan keamanan: kredensial terenkripsi dengan master passphrase saat ini. Jika berbeda, item akan diimpor namun perlu re-entry password.

---

## 12. Logging & Diagnostik
- File log utama: `<base_dir>/logs/app.log` (rotating file handler).
- Informasi yang dicatat: startup, inisialisasi service, pendaftaran jadwal, eksekusi backup, error.
- Pada mode layanan, heartbeat berkala memastikan scheduler tetap aktif.

---

## 13. Troubleshooting
- Backup tidak berjalan saat GUI ditutup:
  - Pastikan Service/Task sudah terpasang (Settings → Setup/Install) dan berjalan.
  - Periksa `<base_dir>/logs/app.log` untuk pesan "Schedule service started" dan eksekusi job.
- Akses UNC gagal:
  - Jalankan layanan sebagai akun user yang memiliki akses share (bukan SYSTEM).
  - Pastikan path `backup.root_folder` valid dan dapat ditulis.
- "Unable to open database file":
  - Pastikan folder `<base_dir>/data` ada dan dapat ditulis.
  - Jalankan EXE dari lokasi yang memiliki izin tulis (bukan lokasi read-only tanpa elevasi).
- Passphrase salah / tidak cocok:
  - Jika passphrase berubah, kredensial lama tidak bisa didekripsi. Edit ulang kredensial dan masukkan ulang password.
- Tidak ada log terbentuk:
  - Pastikan `<base_dir>/logs` dapat ditulis dan level logging sesuai (`INFO`/`DEBUG`).

---

## 14. FAQ
- Apakah aplikasi harus tetap terbuka?  
  Tidak. Setelah layanan di-setup, GUI boleh ditutup. Layanan berjalan 24/7.

- Di mana file backup disimpan?  
  Di `backup.root_folder` (konfigurasi), default struktur folder berdasarkan switch/tanggal.

- Apakah aman menyimpan Auto-Login?  
  Auto-Login menyimpan passphrase secara terenkripsi ringan untuk kemudahan. Gunakan hanya di perangkat tepercaya.

---

## 15. Pembaruan Versi
- Ganti EXE dengan versi baru pada folder yang sama.
- Konfigurasi (`appsettings.yaml`), database (`app.db`), dan folder `backups/` & `logs/` tetap dipakai.
- Jika ada perubahan skema DB, aplikasi akan menangani migrasi ringan secara otomatis.

---

## 16. Kontak & Support
- Periksa `memory.md` untuk catatan perubahan (changelog) dan detail teknis.
- Simak log `<base_dir>/logs/app.log` saat melaporkan masalah.
