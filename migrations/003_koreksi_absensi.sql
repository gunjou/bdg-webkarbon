-- =====================================================================
-- 003: koreksi absensi oleh admin / persetujuan koreksi
--   - absen hasil koreksi tidak punya GPS/foto -> kolom tsb boleh NULL
--   - created_by / updated_by / updated_at: absen dianggap "koreksi" bila
--     user pembuat/pengubah terakhir BUKAN akun pegawai itu sendiri
--   - permission absensi.koreksi untuk ADMIN, SEKDES, KADES
-- Aman dijalankan ulang.
-- =====================================================================
BEGIN;

ALTER TABLE absensi ALTER COLUMN id_lokasi_kantor DROP NOT NULL;
ALTER TABLE absensi ALTER COLUMN latitude         DROP NOT NULL;
ALTER TABLE absensi ALTER COLUMN longitude        DROP NOT NULL;
ALTER TABLE absensi ALTER COLUMN photo_path       DROP NOT NULL;

ALTER TABLE absensi ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users (id_user);
ALTER TABLE absensi ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
ALTER TABLE absensi ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES users (id_user);

UPDATE roles SET permissions = permissions || '["absensi.koreksi"]'::jsonb
WHERE code IN ('ADMIN', 'SEKDES', 'KADES') AND NOT permissions ? 'absensi.koreksi';

COMMIT;
