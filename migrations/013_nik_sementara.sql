-- =====================================================================
-- 013: NIK sementara 9999999999999999 boleh dipakai banyak warga
--   (warga yang NIK aslinya belum diketahui). NIK lain tetap unik.
--   Aman dijalankan ulang.
-- =====================================================================
BEGIN;

DROP INDEX IF EXISTS uq_penduduk_nik;
CREATE UNIQUE INDEX uq_penduduk_nik ON penduduk (nik)
    WHERE nik IS NOT NULL AND nik <> '9999999999999999';

COMMIT;
