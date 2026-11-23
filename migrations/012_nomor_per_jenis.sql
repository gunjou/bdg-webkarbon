-- =====================================================================
-- 012: Nomor urut surat terpisah per jenis surat (format nomor tetap).
--   Karena format {klasifikasi}/{urut}/{kode_desa}/{tahun}, kode klasifikasi
--   harus unik per jenis; jenis yang berbagi 470 diberi kode sendiri
--   (boleh diubah desa lewat master jenis surat). Aman dijalankan ulang.
-- =====================================================================
BEGIN;

INSERT INTO settings (key, value, description, created_at)
VALUES ('surat.cakupan_nomor', '"PER_JENIS"', 'Nomor urut global atau per jenis surat', now())
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now();

UPDATE jenis_surat j SET kode_klasifikasi = v.k, updated_at = now()
FROM (VALUES ('SKL', '470.1'), ('SKK', '470.2'), ('SKBN', '470.3'), ('SKAW', '470.4')) AS v(code, k)
WHERE j.code = v.code AND j.kode_klasifikasi = '470';

ALTER TABLE jenis_surat DROP CONSTRAINT IF EXISTS uq_jenis_surat_klasifikasi;
ALTER TABLE jenis_surat ADD CONSTRAINT uq_jenis_surat_klasifikasi UNIQUE (kode_klasifikasi);

COMMIT;
