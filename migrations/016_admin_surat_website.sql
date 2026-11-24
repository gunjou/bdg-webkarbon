-- =====================================================================
-- 016: role ADMIN dibatasi ke menu /surat, /buku-surat, /website saja
--   (jenis surat & pengaturan kop/penomoran = SUPER_ADMIN).
--   Pegawai, absensi, izin, master, penduduk, akun = SUPER_ADMIN ("*").
--   Data penduduk/ref-options/settings untuk form surat tetap terbuka lewat surat.view/surat.create.
-- Aman dijalankan ulang.
-- =====================================================================
BEGIN;

UPDATE roles SET permissions = '[
    "surat.view", "surat.create", "surat.terbitkan", "surat.cancel", "surat.edit_redaksi",
    "landing.manage"
]'::jsonb
WHERE code = 'ADMIN';

COMMIT;
