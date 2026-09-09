# 05: DG halaman /admin/ncm: fleet + aksi + offline banner

**What to build:**
Halaman `/admin/ncm` per site dengan 4 area: Switches (CRUD), Backups & Schedules (lihat/ubah jadwal, trigger backup, buat baseline), Baselines & Reviews (antrian review drift + diff, approve/reject dengan catatan), Connection (superadmin-only). Status fleet live-fetch dari NCM (transient, tidak disync ke DB). Saat NCM offline: banner "NCM offline — terakhir terlihat <timestamp>" + semua tombol aksi disabled. Semua aksi DG tercatat audit log (Server Action: guard `requireActiveSiteAdminAction` + zod + audit + revalidatePath).

**Blocked by:** 2: NCM write scopes; 4: DG ncmSettings + lib/ncm.ts.

**Status:** ready-for-agent

- [ ] 4 area tampil per site sesuai desain; akses Connection superadmin-only.
- [ ] Setiap aksi (tambah/edit/hapus switch, update password, ubah jadwal, trigger backup, buat baseline, approve/reject review) end-to-end ke NCM test-server.
- [ ] Banner offline + disabled aksi saat NCM tidak terjangkau; `lastSeenAt` terisi.
- [ ] Audit log DG tercatat untuk semua aksi; password tidak pernah muncul di log/UI setelah submit.