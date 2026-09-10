# Tech-debt ticket: webhook NCM dikonfigurasi 100% lewat UI

**Latar:** Setelah tiket 01-07, satu-satunya pengaturan NCM yang masih harus di-HTTP-API-manual adalah `webhook_url` + `webhook_secret` di sisi NCM (runtime_settings.json). User melarang konfigurasi lewat SQL/env/API manual — HARUS lewat UI.

**Arah desain:**
- DG menambah field `ncmWebhookUrl` + `ncmWebhookSecret` di form NCM Connection (per site) yang sudah ada.
- Saat disimpan, DG memanggil `PATCH /api/v1/system/notify-settings` di NCM dengan kredensial JWT admin (bukan API key) — artinya DG perlu menyimpan/meminta kredensial admin NCM ATAU endpoint notify-settings dibuka ke scope baru `system:write`.
- Pilihan lebih bersih: tambah scope `system:write` di NCM (pola KNOWN_SCOPES sudah ada), buka PATCH notify-settings via require_role_or_key, lalu DG pakai admin API key yang sudah tersimpan untuk push konfigurasi webhook. Nol kredensial tambahan di DG.
- Mode "webhook per site" di NCM: runtime_settings.json NCM global (satu webhook per instance NCM) — cocok karena 1 site = 1 instance NCM.
- Runbook + UI text diperbarui; hilangkan instruksi "isi via SQL/API manual".

**Blocked by:** — (semua tiket 01-07 selesai)
**Status:** done (NCM 8a993d8, DG 26436f5)

- [ ] NCM: scope `system:write` valid + PATCH /system/notify-settings menerima API key berscope itu (role check tetap untuk JWT).
- [ ] DG: form NCM Connection punya field webhook URL + secret per site (terenkripsi at-rest di DG, dikirim ke NCM saat save).
- [ ] DG: action `saveNcmWebhook` memanggil PATCH notify-settings NCM pakai admin API key tersimpan; error NCM ditampilkan di form.
- [ ] UI tidak lagi menyebut SQL/manual API; runbook di-update.
- [ ] Test: DG vitest untuk action; NCM pytest untuk scope baru.
