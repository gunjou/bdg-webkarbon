"""Admin menambahkan izin untuk pegawai. DB di-mock."""
import unittest
from unittest.mock import patch

from api.modules.absensi import service
from api.shared.exceptions import ValidationError

JENIS = {"id_jenis_izin": 2, "is_active": 1, "butuh_lampiran": 0}
DATA = {"id_pegawai": 7, "id_jenis_izin": 2, "tanggal_mulai": "2026-11-10", "tanggal_selesai": "2026-11-11", "alasan": " Sakit "}


@patch.object(service.query, "get_pegawai_aktif", return_value=[{"id_pegawai": 7}])
@patch.object(service.presensi.jenis_izin_service, "get", return_value=JENIS)
class TambahIzinTest(unittest.TestCase):
    @patch.object(service, "get_perizinan", return_value={"id_perizinan": 9})
    @patch.object(service.query, "insert_izin_disetujui", return_value=9)
    @patch.object(service.presensi.query, "count_izin_bentrok", return_value=0)
    def test_ok_langsung_disetujui(self, _b, insert, _g, *_):
        self.assertEqual(service.tambah_izin(dict(DATA), None, 1), {"id_perizinan": 9})
        row = insert.call_args.args[0]
        self.assertEqual((row["id_pegawai"], row["alasan"], str(row["tanggal_selesai"])), (7, "Sakit", "2026-11-11"))

    @patch.object(service.presensi.query, "count_izin_bentrok", return_value=1)
    def test_bentrok_ditolak(self, *_):
        with self.assertRaises(ValidationError):
            service.tambah_izin(dict(DATA), None, 1)


if __name__ == "__main__":
    unittest.main()
