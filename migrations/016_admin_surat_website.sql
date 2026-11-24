-- =====================================================================
-- 016: role ADMIN dibatasi ke persuratan + website desa saja.
--   Pegawai, absensi, izin, master, penduduk, akun = SUPER_ADMIN ("*").
--   Data penduduk/ref-options/settings untuk form surat tetap terbuka lewat surat.view/surat.create.
-- Aman dijalankan ulang.
-- =====================================================================
BEGIN;

UPDATE roles SET permissions = '[
    "jenis_surat.manage",
    "surat.view", "surat.create", "surat.terbitkan", "surat.cancel", "surat.edit_redaksi",
    "settings.surat_manage",
    "landing.manage"
]'::jsonb
WHERE code = 'ADMIN';

COMMIT;
