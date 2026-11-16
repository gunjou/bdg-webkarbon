"""Validasi pengaturan desa & surat. DB di-mock."""
import unittest
from unittest.mock import patch

from api.modules.settings import service
from api.shared.exceptions import ValidationError


@patch.object(service.query, "get_values", return_value={"desa.nama": "X"})
@patch.object(service.query, "upsert")
class SettingsTest(unittest.TestCase):
    def test_default_ditimpa_db(self, _u, _g):
        cfg = service.get_all()
        self.assertEqual((cfg["desa.nama"], cfg["surat.kode_desa"]), ("X", "KRB"))

    def test_normalisasi(self, upsert, _):
        service.update({"surat.kode_desa": " krb ", "surat.cakupan_nomor": "per_jenis"}, 1)
        self.assertEqual(upsert.call_args.args[0], {"surat.kode_desa": "KRB", "surat.cakupan_nomor": "PER_JENIS"})

    def test_format_nomor(self, upsert, _):
        for bad in ("{klasifikasi}/{kode_desa}", "{urut}/{bulan}"):
            with self.assertRaises(ValidationError):
                service.update({"surat.format_nomor": bad}, 1)
        upsert.assert_not_called()

    def test_key_asing_dan_logo_ditolak(self, *_):
        for k in ("foo", "desa.logo_path"):
            with self.assertRaises(ValidationError):
                service.update({k: "x"}, 1)

    def test_logo_bukan_gambar(self, *_):
        with self.assertRaises(ValidationError):
            service.set_logo(b"bukan gambar", 1)


if __name__ == "__main__":
    unittest.main()
