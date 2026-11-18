import unittest
from unittest.mock import patch

from api.modules.notifikasi import service

IZIN = (3, [{"id_perizinan": 9}])
SURAT = (2, [{"id_surat": 33}])


@patch("api.modules.notifikasi.service.query.surat_draft", return_value=SURAT)
@patch("api.modules.notifikasi.service.query.perizinan_menunggu", return_value=IZIN)
class RingkasanTest(unittest.TestCase):
    def test_super_admin_dapat_keduanya(self, izin, surat):
        r = service.ringkasan({"*"}, None)
        self.assertEqual((r["perizinan"]["jumlah"], r["surat"]["jumlah"]), (3, 2))

    def test_kades_hanya_perizinan_dan_pengajuan_sendiri_dikecualikan(self, izin, surat):
        r = service.ringkasan({"perizinan.view_all", "perizinan.review"}, 7)
        self.assertIsNone(r["surat"])
        izin.assert_called_once_with(7, service.LIMIT)
        surat.assert_not_called()

    def test_operator_surat_hanya_surat(self, izin, surat):
        r = service.ringkasan({"surat.create"}, None)
        self.assertIsNone(r["perizinan"])
        self.assertEqual(r["surat"]["items"], [{"id_surat": 33}])
        izin.assert_not_called()


if __name__ == "__main__":
    unittest.main()
