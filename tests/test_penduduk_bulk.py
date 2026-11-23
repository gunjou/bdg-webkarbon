"""Impor bulk penduduk. DB di-mock."""
import unittest
from unittest.mock import patch

from api.modules.master.ref_options import service as ref
from api.modules.penduduk import service

AKTIF = {"AGAMA": set(), "PEKERJAAN": set(), "STATUS_PERKAWINAN": set(), "KEWARGANEGARAAN": {"WNI"},
         "DUSUN": {"KARANG_BONGKOT"}}
A = {"full_name": "YUSUF", "nik": "5201080608790001", "dusun": "KARANG_BONGKOT", "rt": "5"}
B = {"full_name": "NUR", "nik": "5201085206790005", "dusun": "KARANG_BONGKOT"}


@patch.object(ref.query, "get_active_codes", return_value=AKTIF)
@patch.object(service.query, "find_by_nik", return_value=None)
@patch.object(service.query, "insert_many")
class PendudukBulkTest(unittest.TestCase):
    def test_semua_valid_tersimpan(self, ins, *_):
        r = service.bulk([A, B], False, 1)
        self.assertTrue(r["saved"])
        self.assertEqual(ins.call_args[0][0][0]["rt"], "005")

    def test_dry_run_tidak_simpan(self, ins, *_):
        self.assertFalse(service.bulk([A, B], True, 1)["saved"])
        ins.assert_not_called()

    def test_nik_ganda_di_file_dan_db(self, ins, find, _):
        find.side_effect = lambda nik, _=None: {"full_name": "LAMA", "is_active": 1} if nik == B["nik"] else None
        r = service.bulk([A, B, A, {"full_name": ""}], False, 1)
        self.assertEqual([e["baris"] for e in r["errors"]], [2, 3, 4])
        self.assertIn("LAMA", r["errors"][0]["message"])
        ins.assert_not_called()

    def test_dusun_tidak_ada(self, ins, *_):
        r = service.bulk([{**A, "dusun": "X"}], False, 1)
        self.assertEqual(r["errors"][0]["errors"], {"dusun": "Pilihan tidak valid (DUSUN)"})


if __name__ == "__main__":
    unittest.main()
