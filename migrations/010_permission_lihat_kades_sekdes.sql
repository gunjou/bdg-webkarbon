-- =====================================================================
-- 010: KADES & SEKDES bisa MELIHAT semua manajemen (absensi, persuratan,
--   penduduk), tanpa master, pengaturan, akun/role. Verifikasi/tanda tangan
--   surat tetap manual di kertas. Akun multi-role tetap mendapat gabungan
--   permission (mis. SEKDES + ADMIN = hak ADMIN).
-- Aman dijalankan ulang.
-- =====================================================================
BEGIN;

UPDATE roles r
SET permissions = (
    SELECT jsonb_agg(DISTINCT p)
    FROM jsonb_array_elements(r.permissions || '[
        "absensi_gagal.view", "surat.view", "penduduk.view"
    ]'::jsonb) AS p
)
WHERE r.code IN ('SEKDES', 'KADES');

COMMIT;
