-- =====================================================================
-- 017: cabut jenis_surat.manage & settings.surat_manage dari ADMIN
--   (016 sudah tercatat di schema_migrations sebelum diubah, jadi perubahannya tidak ikut jalan).
--   ADMIN = menu /surat, /buku-surat, /website saja. Aman dijalankan ulang.
-- =====================================================================
BEGIN;

UPDATE roles SET permissions = '[
    "surat.view", "surat.create", "surat.terbitkan", "surat.cancel", "surat.edit_redaksi",
    "landing.manage"
]'::jsonb
WHERE code = 'ADMIN';

COMMIT;
