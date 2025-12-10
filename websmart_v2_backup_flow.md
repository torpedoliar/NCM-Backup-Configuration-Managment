# Alur Backup WebSmart V2 (Allied Telesis)

Dokumen ini menjelaskan alur teknis proses backup untuk switch Allied Telesis WebSmart V2 (seperti GS950/52PS V2) yang menggunakan enkripsi RSA dan login berbasis API.

## Ringkasan Proses

Proses backup dilakukan oleh class `WebSmartClient` di `app/net/web_smart_client.py`. Berbeda dengan model lama yang menggunakan form POST sederhana, model V2 membutuhkan enkripsi RSA untuk kredensial dan menggunakan token sesi (Gambit) untuk otentikasi request selanjutnya.

## Detail Flow

### 1. Inisialisasi
- **Input**: Host (IP), Port (default 80), Username, Password.
- **Deteksi**: Jika protokol diset ke `websmart-v2` di `runner.py`, sistem akan memaksa penggunaan logika V2 (`force_v2_only=True`).

### 2. Otentikasi (Login)
Proses login V2 (`_try_v2_login`) terdiri dari beberapa langkah:

#### a. Pengambilan Public Key
- **Request**: GET ke `/iss/specific/web_pub_key_data.js`
- **Tujuan**: Mendapatkan RSA Public Key yang disediakan oleh switch.
- **Parsing**: Regex digunakan untuk mengekstrak blok kunci PEM dari respon JavaScript.

#### b. Enkripsi Kredensial
- Menggunakan library `Crypto.PublicKey.RSA` dan `Crypto.Cipher.PKCS1_v1_5`.
- **Username** dienkripsi dan di-encode base64 menjadi parameter `pelican`.
- **Password** dienkripsi dan di-encode base64 menjadi parameter `pinkpanther`.

#### c. Pengiriman Login Data
- **Request**: GET ke `/iss/specific/web_login_data.js`
- **Parameter**: 
  - `pelican`: Username terenkripsi
  - `pinkpanther`: Password terenkripsi
- **Headers**: Header `Accept` diubah sementara menjadi `application/json` untuk mengharapkan balasan JSON.

#### d. Validasi & Token
- **Respon**: JSON yang berisi token sesi.
- **Ekstraksi**: Token diambil dari field `gambit` dalam respon JSON.
- Token ini disimpan (`self.gambit_token`) untuk digunakan pada request download.

### 3. Pengambilan Konfigurasi (Backup)
Setelah login berhasil dan token didapatkan:

- **Target URL**: Sistem mencoba endpoint download berikut secara berurutan:
  1. `iss1.conf?Gambit={TOKEN}` (Standard V2)
  2. `iss.conf?Gambit={TOKEN}` (Fallback)
  
- **Proses Download**:
  - Melakukan GET request ke URL target.
  - Memeriksa `Content-Type` header.
  - Jika konten berupa text/binary (bukan HTML error page) dan ukurannya valid (>100 bytes), file dianggap berhasil didownload.

### 4. Normalisasi
- Output konfigurasi dibersihkan dari karakter `\r` (carriage return) untuk memastikan format line-ending Unix (`\n`) yang konsisten.
- Spasi berlebih di awal/akhir baris dan baris kosong di awal/akhir file dihapus.

### 5. Selesai
- Koneksi ditutup.
- File konfigurasi siap disimpan ke disk.

## Diagram Alur

### Sequence Diagram

```mermaid
sequenceDiagram
    participant App as Aplikasi Backup
    participant Switch as Switch WebSmart V2
    
    Note over App: Mulai Backup (WebSmart V2)
    
    App->>Switch: GET /iss/specific/web_pub_key_data.js
    Switch-->>App: Return JS (RSA Public Key)
    
    Note over App: Enkripsi User & Pass dengan RSA
    
    App->>Switch: GET /iss/specific/web_login_data.js?pelican=...&pinkpanther=...
    Switch-->>App: Return JSON { "gambit": "TOKEN_SESI" }
    
    Note over App: Simpan Token Gambit
    
    App->>Switch: GET /iss1.conf?Gambit=TOKEN_SESI
    Switch-->>App: Return File Config (Binary/Text)
    
    Note over App: Normalisasi & Simpan File
```

### Flowchart Proses

![Flowchart proses backup WebSmart V2](C:/Users/IT10/.gemini/antigravity/brain/39af1da0-18e9-41f8-a9b0-8c6787b18bc7/websmart_v2_flowchart_1764120692888.png)

```mermaid
flowchart TD
    Start([Mulai Backup WebSmart V2]) --> Init[Inisialisasi WebSmartClient<br/>force_v2_only=True]
    Init --> GetKey[GET /iss/specific/web_pub_key_data.js]
    
    GetKey --> CheckKey{Status 200?}
    CheckKey -->|No| LoginFail[Login Gagal]
    CheckKey -->|Yes| ParseKey[Parse RSA Public Key<br/>dari JavaScript]
    
    ParseKey --> CheckParse{Key Found?}
    CheckParse -->|No| LoginFail
    CheckParse -->|Yes| Encrypt[Enkripsi Username & Password<br/>dengan RSA PKCS1_v1_5]
    
    Encrypt --> CheckLib{Library<br/>pycryptodome<br/>tersedia?}
    CheckLib -->|No| LoginFail
    CheckLib -->|Yes| Base64[Encode Base64<br/>pelican & pinkpanther]
    
    Base64 --> SendLogin[GET /iss/specific/web_login_data.js<br/>?pelican=...&pinkpanther=...]
    SendLogin --> CheckLogin{Status 200?}
    CheckLogin -->|No| LoginFail
    CheckLogin -->|Yes| ParseJSON[Parse JSON Response]
    
    ParseJSON --> CheckGambit{Field 'gambit'<br/>ada?}
    CheckGambit -->|No| LoginFail
    CheckGambit -->|Yes| SaveToken[Simpan Gambit Token]
    
    SaveToken --> TryDownload1[GET /iss1.conf?Gambit=TOKEN]
    TryDownload1 --> Check1{Status 200 &<br/>Size > 100?}
    Check1 -->|Yes| Success[Config Berhasil]
    Check1 -->|No| TryDownload2[GET /iss.conf?Gambit=TOKEN]
    
    TryDownload2 --> Check2{Status 200 &<br/>Size > 100?}
    Check2 -->|Yes| Success
    Check2 -->|No| DownloadFail[Download Gagal]
    
    Success --> Normalize[Normalisasi Output<br/>- Hapus \\r<br/>- Trim whitespace<br/>- Hapus baris kosong]
    Normalize --> Save[Simpan File ke Disk]
    Save --> End([Selesai - Backup Sukses])
    
    LoginFail --> RetryCheck{Sudah Max<br/>Retries?}
    RetryCheck -->|No| Wait[Tunggu dengan<br/>Backoff Delay]
    Wait --> GetKey
    RetryCheck -->|Yes| ErrorEnd([Error - Login Gagal])
    
    DownloadFail --> ErrorEnd2([Error - Download Gagal])
    
    style Start fill:#90EE90
    style End fill:#90EE90
    style ErrorEnd fill:#FFB6C1
    style ErrorEnd2 fill:#FFB6C1
    style LoginFail fill:#FFA07A
    style DownloadFail fill:#FFA07A
```

