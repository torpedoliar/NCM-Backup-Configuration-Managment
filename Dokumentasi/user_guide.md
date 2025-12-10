# Panduan Pengguna - Allied Telesis Switch Backup Manager

Aplikasi ini dirancang untuk mempermudah proses backup konfigurasi switch Allied Telesis, baik secara manual maupun terjadwal. Aplikasi ini mendukung berbagai protokol termasuk SSH, Telnet, dan WebSmart (V1 & V2).

## Daftar Isi
1. [Persiapan Awal](#persiapan-awal)
2. [Dashboard](#dashboard)
3. [Manajemen Kredensial](#manajemen-kredensial)
4. [Manajemen Inventory Switch](#manajemen-inventory-switch)
5. [Melakukan Backup](#melakukan-backup)
6. [Jadwal Backup Otomatis](#jadwal-backup-otomatis)
7. [Melihat Riwayat & Perubahan (Diff)](#melihat-riwayat--perubahan-diff)
8. [Pengaturan Aplikasi](#pengaturan-aplikasi)

---

## Persiapan Awal

Saat pertama kali aplikasi dijalankan, Anda akan diminta untuk membuat **Master Passphrase**.
*   **Penting**: Passphrase ini digunakan untuk mengenkripsi semua password switch yang tersimpan.
*   Jangan sampai lupa passphrase ini. Jika hilang, Anda harus mereset database dan memasukkan ulang semua kredensial.

---

## Dashboard

Halaman utama (Dashboard) memberikan ringkasan status sistem:
*   **Total Switches**: Jumlah switch yang terdaftar.
*   **Success Rate**: Persentase keberhasilan backup dalam 24 jam terakhir.
*   **Storage Usage**: Penggunaan ruang disk oleh file backup.
*   **Recent Activity**: Log aktivitas terbaru (backup sukses/gagal).

---

## Manajemen Kredensial

Sebelum menambahkan switch, Anda perlu mendaftarkan kredensial (username/password) yang akan digunakan.

1.  Masuk ke tab **Credentials**.
2.  Klik **➕ Add Credential**.
3.  Isi form berikut:
    *   **Name**: Nama label untuk kredensial ini (contoh: `Admin-Lantai1`).
    *   **Username**: Username login switch.
    *   **Password**: Password login switch.
    *   **Enable Password**: (Opsional) Password untuk masuk ke mode privileged exec (`enable`).
4.  Klik **Save**.

---

## Manajemen Inventory Switch

Tab **Inventory** adalah tempat Anda mengelola daftar perangkat switch.

### Menambahkan Switch
1.  Klik **➜ Add Switch**.
2.  Isi detail switch:
    *   **Name**: Nama hostname atau label switch.
    *   **IP/FQDN**: Alamat IP switch.
    *   **Protocol**: Pilih protokol yang sesuai:
        *   `SSH`: Untuk switch modern (Port 22).
        *   `Telnet`: Untuk switch lama (Port 23).
        *   `WebSmart`: Untuk switch WebSmart generasi lama (HTTP).
        *   `WebSmart V2`: Untuk switch WebSmart baru (seperti GS950/52PS V2) yang menggunakan enkripsi RSA.
    *   **Port**: Port default akan terisi otomatis sesuai protokol, namun bisa diubah jika perlu.
    *   **Credential**: Pilih kredensial yang sudah dibuat sebelumnya.
3.  Klik **Save**.

### Import Banyak Switch (Batch Import)
Anda bisa memasukkan banyak switch sekaligus menggunakan file CSV.
1.  Klik **📋 Batch Import**.
2.  Pilih file `.csv` dengan format kolom:
    ```csv
    name,ip,protocol,port,credential_name,notes
    Switch-Utama,192.168.1.1,ssh,22,Admin-Lantai1,Switch Core
    Switch-Lobby,192.168.1.2,websmart-v2,80,Admin-Web,Switch Tamu
    ```
3.  Aplikasi akan memproses dan melaporkan hasilnya.

---

## Melakukan Backup

### Backup Manual
1.  Di tab **Inventory**, pilih switch yang ingin dibackup.
2.  Klik tombol **📥 Get Data**.
3.  Proses akan berjalan di latar belakang (background).
4.  Pantau status di panel **Backup Console** di sebelah kanan bawah.
    *   Jika sukses, status akan berubah menjadi `✓ OK`.
    *   Jika gagal, pesan error akan muncul di console.

### Console Langsung (Live Console)
Untuk troubleshooting koneksi SSH/Telnet:
1.  Pilih switch di Inventory.
2.  Klik **🖧 SSH Console** atau **☎ Telnet Console**.
3.  Jendela terminal akan terbuka untuk mencoba login manual.

---

## Jadwal Backup Otomatis

Anda dapat mengatur agar backup berjalan otomatis secara berkala.

1.  Masuk ke tab **Schedules**.
2.  Klik **➕ Add Schedule**.
3.  Pilih **Switch** yang akan dijadwalkan.
4.  Pilih **Schedule Type**:
    *   **Interval**: Berjalan setiap X menit/jam (contoh: Setiap 6 jam).
    *   **Daily**: Berjalan setiap hari pada jam tertentu (contoh: 23:00).
    *   **Weekly**: Berjalan seminggu sekali pada hari dan jam tertentu.
    *   **Monthly**: Berjalan sebulan sekali pada tanggal dan jam tertentu.
5.  Klik **Save**.

Pastikan status jadwal adalah **Enabled** (✓).

---

## Melihat Riwayat & Perubahan (Diff)

Aplikasi menyimpan riwayat backup dan dapat membandingkan perubahan konfigurasi.

1.  Masuk ke tab **History**.
2.  Pilih switch dari dropdown di kiri atas.
3.  Daftar backup yang tersedia akan muncul.
4.  **Melihat Isi Config**: Pilih satu backup, lalu klik **👁️ View Content**.
5.  **Membandingkan Perubahan (Diff)**:
    *   Pilih **dua** baris backup (tahan tombol `Ctrl` saat klik).
    *   Klik **⚖️ Show Diff**.
    *   Aplikasi akan menampilkan perbandingan *Side-by-Side* atau *Unified Diff*. Baris hijau adalah penambahan, merah adalah penghapusan.

---

## Pengaturan Aplikasi

Di tab **Settings**, Anda dapat mengatur:
*   **Backup Retention**: Berapa lama file backup disimpan (default 30 hari). File lebih lama akan otomatis dihapus untuk menghemat ruang.
*   **Connection Timeout**: Batas waktu tunggu koneksi (default 30 detik).
*   **Prompt Patterns**: Pola regex untuk mendeteksi prompt CLI switch (untuk SSH/Telnet). Berguna jika Anda memiliki switch dengan prompt non-standar.

---

## Troubleshooting Umum

*   **Login Failed**: Periksa username/password di tab Credentials. Pastikan akun tidak terkunci di switch.
*   **Connection Timeout**: Pastikan IP switch bisa diping dari komputer ini. Cek firewall.
*   **WebSmart V2 Error**: Pastikan memilih protokol `WebSmart V2` (bukan WebSmart biasa) untuk switch tipe baru yang menggunakan login berbasis RSA/JavaScript.
