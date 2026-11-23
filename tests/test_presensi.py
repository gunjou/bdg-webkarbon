"""Aturan presensi (jadwal, GPS, wajah). DB di-mock."""
import unittest
from datetime import datetime
from unittest.mock import patch

from api.modules.presensi import service
from api.shared.exceptions import AppError

CFG = dict(service.DEFAULT_SETTINGS)
CTX = {"id_pegawai": 7, "libur": None, "toleransi_terlambat_menit": 15,
       "jadwal_harian": {"senin": {"masuk": "07:30", "pulang": "15:30"}}}
LOK = [{"id_lokasi_kantor": 1, "name": "Kantor", "latitude": -8.5, "longitude": 116.1, "radius_meter": 100}]
SENIN = datetime(2026, 11, 9)


@patch.object(service.query, "insert_gagal")
class PresensiTest(unittest.TestCase):
    def jadwal(self, jam, jenis="masuk", done=()):
        h, m = jam
        return service._cek_jadwal(CTX, jenis, SENIN.replace(hour=h, minute=m), set(done), CFG)

    def test_jadwal(self, _):
        self.assertEqual(self.jadwal((7, 45))["status"], "tepat_waktu")
        self.assertEqual(self.jadwal((7, 46))["terlambat_menit"], 16)
        for jam in ((6, 29), (15, 30)):
            with self.assertRaises(AppError):
                self.jadwal(jam)
        with self.assertRaises(AppError):
            self.jadwal((10, 0), "pulang")  # belum masuk
        with self.assertRaises(AppError):
            self.jadwal((16, 0), "pulang")  # lupa masuk: tetap ditolak walau jam pulang sudah lewat
        self.assertEqual(self.jadwal((16, 0), "pulang", done=["masuk"])["status"], "tepat_waktu")
        self.assertEqual(self.jadwal((10, 0), "pulang", done=["masuk"])["status"], "pulang_cepat")

    @patch.object(service.query, "get_lokasi_aktif", return_value=LOK)
    def test_gps_nan_ditolak(self, *_):
        nan = float("nan")
        for lat, lon, akurasi in ((nan, nan, 10.0), (-8.5, 116.1, nan), (-8.5, 116.1, -1.0), (-9.5, 116.1, 10.0)):
            with self.subTest(lat=lat, lon=lon, akurasi=akurasi), self.assertRaises(AppError):
                service._cek_lokasi(CTX, "masuk", lat, lon, akurasi, CFG)

    @patch.object(service.query, "get_lokasi_aktif", return_value=LOK)
    def test_gps_inf_bukan_500(self, *_):
        with self.assertRaises(AppError):
            service._cek_lokasi(CTX, "masuk", float("inf"), 116.1, 10.0, CFG)


if __name__ == "__main__":
    unittest.main()
