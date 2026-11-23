"""Validasi penduduk & ref_options. DB di-mock."""
import unittest
from unittest.mock import patch

from api.modules.master.ref_options import service as ref
from api.modules.penduduk import service
from api.shared.exceptions import ValidationError

AKTIF = {"AGAMA": {"ISLAM"}, "PEKERJAAN": set(), "STATUS_PERKAWINAN": set(), "KEWARGANEGARAAN": {"WNI"}, "DUSUN": set()}


@patch.object(ref.query, "get_active_codes", return_value=AKTIF)
@patch.object(service.query, "find_by_nik", return_value=None)
class PendudukCleanTest(unittest.TestCase):
    def test_normalisasi(self, *_):
        out = service._clean({"full_name": " Gugun ", "agama": "islam", "rt": "2", "nik": "", "jenis_kelamin": "l",
                              "tanggal_lahir": "1998-11-03"})
        self.assertEqual((out["full_name"], out["agama"], out["rt"], out["nik"], out["kewarganegaraan"],
                          out["jenis_kelamin"], str(out["tanggal_lahir"])),
                         ("Gugun", "ISLAM", "002", None, "WNI", "L", "1998-11-03"))

    def test_kode_ref_tidak_aktif(self, *_):
        with self.assertRaises(ValidationError) as e:
            service._clean({"full_name": "A", "agama": "HINDU"})
        self.assertIn("agama", e.exception.errors)

    def test_kode_lama_nonaktif_tetap_boleh_saat_edit(self, *_):
        current = {"id_penduduk": 1, "agama": "HINDU", "pekerjaan": None, "status_perkawinan": None,
                   "kewarganegaraan": "WNI", "dusun": None}
        self.assertEqual(service._clean({"full_name": "A", "agama": "HINDU"}, current)["agama"], "HINDU")
        with self.assertRaises(ValidationError):
            service._clean({"full_name": "A", "agama": "KATOLIK"}, current)

    def test_nik_bukan_16_digit(self, *_):
        with self.assertRaises(ValidationError):
            service._clean({"full_name": "A", "nik": "123"})

    def test_nik_duplikat(self, find, _):
        find.return_value = {"id_penduduk": 3, "full_name": "B", "is_active": 1}
        with self.assertRaises(ValidationError):
            service._clean({"full_name": "A", "nik": "5201010101010001"})


class PendudukSearchTest(unittest.TestCase):
    @patch.object(service.query, "search", return_value=([], 0))
    def test_angka_cari_nomor_nama_lowercase(self, search):
        self.assertEqual(service.search({"q": "5201", "limit": 999}), ([], {"total": 0, "limit": 200, "offset": 0}))
        f = search.call_args.args[0]
        self.assertEqual((f["nomor"], f["nama"], f["limit"]), ("5201", None, 200))
        service.search({"q": "Gugun"})
        self.assertEqual(search.call_args.args[0]["nama"], "gugun")


class RefOptionTest(unittest.TestCase):
    SYS = {"id_ref_option": 1, "group_code": "AGAMA", "code": "ISLAM", "is_system": 1}

    @patch.object(ref.query, "find_by_code", return_value=None)
    def test_opsi_bawaan_kode_tetap(self, _):
        with self.assertRaises(ValidationError):
            ref._clean({"group_code": "AGAMA", "code": "MUSLIM", "label": "x"}, self.SYS)
        self.assertEqual(ref._clean({"group_code": "agama", "code": "islam", "label": " Islam "}, self.SYS)["label"],
                         "Islam")

    @patch.object(ref.query, "get_by_id", return_value=SYS)
    def test_opsi_bawaan_tidak_bisa_nonaktif(self, _):
        with self.assertRaises(ValidationError):
            ref.deactivate(1, 1)


if __name__ == "__main__":
    unittest.main()
