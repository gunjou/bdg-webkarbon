"""Status koreksi dihitung dari jadwal pegawai. DB di-mock."""
import unittest
from datetime import date, time
from unittest.mock import patch

from api.modules.absensi import service
from api.shared.exceptions import ValidationError

PEG = {"jadwal_harian": {"senin": {"masuk": "07:30", "pulang": "15:30"}, "minggu": None}, "toleransi_terlambat_menit": 15}
SENIN, MINGGU = date(2026, 11, 9), date(2026, 11, 8)


@patch.object(service.query, "get_pegawai_aktif", return_value=[PEG])
class KoreksiStatusTest(unittest.TestCase):
    def row(self, jenis, jam, tgl=SENIN, libur=None):
        with patch.object(service.query, "get_libur", return_value=libur or {}):
            return service._koreksi_row(7, tgl, jenis, jam)

    def test_masuk(self, _):
        self.assertEqual(self.row("masuk", time(7, 45))["status"], "tepat_waktu")  # pas toleransi
        r = self.row("masuk", time(7, 46))
        self.assertEqual((r["status"], r["terlambat_menit"], r["jam_jadwal"]), ("terlambat", 16, time(7, 30)))

    def test_pulang(self, _):
        self.assertEqual(self.row("pulang", time(15, 0))["status"], "pulang_cepat")
        self.assertEqual(self.row("pulang", time(15, 30))["status"], "tepat_waktu")

    def test_libur_dan_bukan_hari_kerja_ditolak(self, _):
        with self.assertRaises(ValidationError):
            self.row("masuk", time(7, 30), libur={SENIN: "Libur Nasional"})
        with self.assertRaises(ValidationError):
            self.row("masuk", time(7, 30), tgl=MINGGU)


if __name__ == "__main__":
    unittest.main()
