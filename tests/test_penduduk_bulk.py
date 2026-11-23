"""Impor bulk penduduk. DB di-mock."""
import unittest
from unittest.mock import patch

from api.modules.master.ref_options import service as ref
from api.modules.penduduk import service
from api.shared.exceptions import ValidationError

AKTIF = {"AGAMA": set(), "PEKERJAAN": set(), "STATUS_PERKAWINAN": set(), "KEWARGANEGARAAN": {"WNI"},
         "DUSUN": {"KARANG_BONGKOT"}}
A = {"full_name": "YUSUF", "nik": "5201080608790001", "dusun": "KARANG_BONGKOT", "rt": "5"}
B = {"full_name": "NUR", "nik": "5201085206790005", "dusun": "KARANG_BONGKOT"}


@patch.object(ref.query, "get_active_codes", return_value=AKTIF)
@patch.object(service.query, "find_by_niks", return_value={})
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
        find.return_value = {B["nik"]: {"full_name": "LAMA", "is_active": 1}}
        r = service.bulk([A, B, A, {"full_name": ""}], False, 1)
        self.assertEqual([e["baris"] for e in r["errors"]], [2, 3, 4])
        self.assertIn("LAMA", r["errors"][0]["message"])
        ins.assert_not_called()

    def test_dusun_tidak_ada(self, ins, *_):
        r = service.bulk([{**A, "dusun": "X"}], False, 1)
        self.assertEqual(r["errors"][0]["errors"], {"dusun": "Pilihan tidak valid (DUSUN)"})

    def test_query_tetap_sekali_untuk_banyak_baris(self, ins, find, codes):
        rows = [{"full_name": "W", "nik": f"52010806087{i:05d}"} for i in range(10000)]
        self.assertTrue(service.bulk(rows, False, 1)["saved"])
        self.assertEqual((find.call_count, codes.call_count, len(ins.call_args[0][0])), (1, 1, 10000))

    def test_nik_sementara_boleh_ganda(self, ins, find, _):
        find.return_value = {service.NIK_SEMENTARA: {"full_name": "LAMA", "is_active": 1}}
        t = {"full_name": "X", "nik": service.NIK_SEMENTARA}
        self.assertTrue(service.bulk([t, t], False, 1)["saved"])

    def test_lebih_dari_batas(self, *_):
        with self.assertRaises(ValidationError):
            service.bulk([A] * 10001, True, 1)


if __name__ == "__main__":
    unittest.main()
