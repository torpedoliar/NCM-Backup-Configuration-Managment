Diagram ini menunjukkan integrasi service Windows dengan Task Scheduler dan mekanisme lock untuk mencegah multiple scheduler instances.

Keterangan:
- Task Scheduler: Menjalankan EXE sebagai SYSTEM saat boot.
- Lock: File lock di `data/scheduler.lock` untuk memastikan hanya satu instance scheduler yang berjalan.
- Stale Lock: Jika lock lebih tua dari 3 menit, service akan mengambil alih.
- Service Control: Service diatur oleh Windows Service Control Manager (SCM).
