-- =====================================================================
-- 005: permission modul persuratan
--   Tidak ada role OPERATOR terpisah: tugas operator surat digabung ke ADMIN.
--   SUPER_ADMIN sudah punya "*".
-- Aman dijalankan ulang.
-- =====================================================================
BEGIN;

UPDATE roles r
SET permissions = (
    SELECT jsonb_agg(DISTINCT p)
    FROM jsonb_array_elements(r.permissions || '[
        "jenis_surat.manage",
        "surat.view", "surat.create", "surat.terbitkan", "surat.cancel", "surat.edit_redaksi",
        "penduduk.view", "penduduk.manage",
        "ref_option.manage"
    ]'::jsonb) AS p
)
WHERE r.code = 'ADMIN';

COMMIT;
