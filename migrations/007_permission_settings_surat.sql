-- =====================================================================
-- 007: permission settings.surat_manage (pengaturan desa & surat) untuk ADMIN.
--   Nilai default ada di kode (api/modules/settings/service.py REGISTRY);
--   baris settings baru dibuat saat pertama kali disimpan dari UI.
-- Aman dijalankan ulang.
-- =====================================================================
BEGIN;

UPDATE roles SET permissions = permissions || '["settings.surat_manage"]'::jsonb
WHERE code = 'ADMIN' AND NOT permissions ? 'settings.surat_manage';

COMMIT;
