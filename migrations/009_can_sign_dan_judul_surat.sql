-- =====================================================================
-- 009: (1) nilai awal jabatan penandatangan surat (can_sign)
--      (2) surat.judul : salinan judul (jenis_surat.name) saat draft dibuat, supaya judul surat lama
--          tidak ikut berubah bila nama jenis surat diganti.
-- Aman dijalankan ulang.
-- =====================================================================
BEGIN;

-- selanjutnya can_sign dikelola admin dari menu Jabatan
UPDATE jabatan SET can_sign = 1
WHERE lower(name) IN ('kepala desa', 'sekretaris desa') AND can_sign = 0;

ALTER TABLE surat ADD COLUMN IF NOT EXISTS judul VARCHAR(150);

UPDATE surat s SET judul = js.name
FROM jenis_surat js
WHERE js.id_jenis_surat = s.id_jenis_surat AND s.judul IS NULL;

ALTER TABLE surat ALTER COLUMN judul SET NOT NULL;

COMMIT;
