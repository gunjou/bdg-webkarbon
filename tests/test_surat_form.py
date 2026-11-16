"""Validasi isian surat terhadap skema. Tanpa DB."""
import unittest
from unittest.mock import patch

from api.modules.jenis_surat import form, service as js
from api.modules.surat import service
from api.shared.exceptions import ValidationError

SKEMA = js.validate_skema({"sections": [
    {"key": "pemohon", "label": "Pemohon", "type": "penduduk"},
    {"key": "lain", "label": "Lain", "type": "fields", "fields": [
        {"key": "keperluan", "label": "Keperluan", "type": "text", "required": True},
        {"key": "harga", "label": "Harga", "type": "rupiah"},
        {"key": "tgl", "label": "Tgl", "type": "date"},
        {"key": "jenis", "label": "Jenis", "type": "select", "options": ["Sawah", "Kebun"]}]},
    {"key": "batas", "label": "Batas", "type": "daftar", "columns": [
        {"key": "arah", "label": "Arah", "type": "text", "required": True}, {"key": "luas", "label": "Luas", "type": "number"}]},
    {"key": "catatan", "label": "Catatan", "type": "teks_bebas", "required": True},
]})
OK_CODES = lambda codes: None  # noqa: E731


class FormTest(unittest.TestCase):
    def test_normalisasi_draft(self):
        d = form.validate_data(SKEMA, {
            "pemohon": {"nama": " Gugun ", "rt": "2", "jenis_kelamin": "l", "agama": "islam", "id_penduduk": "7"},
            "harga": "50.000.000", "tgl": "2026-01-02", "asing": 1,
            "batas": [{"arah": "Utara", "luas": "1,5"}, {"arah": "", "luas": None}],
            "catatan": "<p onclick=x>Hai</p><script>1</script>"}, OK_CODES)
        p = d["pemohon"]
        self.assertEqual((p["nama"], p["rt"], p["jenis_kelamin"], p["agama"], p["id_penduduk"]),
                         ("Gugun", "002", "L", "ISLAM", 7))
        self.assertEqual((d["harga"], d["batas"], d["catatan"], d["keperluan"]),
                         (50000000, [{"arah": "Utara", "luas": 1.5}], "<p>Hai</p>", None))
        self.assertNotIn("asing", d)

    def test_format_salah(self):
        with self.assertRaises(ValidationError) as e:
            form.validate_data(SKEMA, {"pemohon": {"nik": "12"}, "tgl": "kemarin", "jenis": "Laut", "harga": "-5"}, OK_CODES)
        self.assertEqual(set(e.exception.errors), {"pemohon.nik", "tgl", "jenis", "harga"})

    def test_strict_wajib(self):
        with self.assertRaises(ValidationError) as e:
            form.validate_data(SKEMA, {"batas": [{"luas": 2}]}, OK_CODES, strict=True)
        self.assertEqual(set(e.exception.errors), {"pemohon.nama", "keperluan", "batas[0].arah", "catatan"})

    def test_kode_ref_dicek(self):
        def tolak(codes):
            raise ValidationError("x", {k: "Pilihan tidak valid" for k in codes})
        with self.assertRaises(ValidationError) as e:
            form.validate_data(SKEMA, {"pemohon": {"agama": "X"}}, tolak)
        self.assertIn("pemohon.agama", e.exception.errors)


class PenandatanganTest(unittest.TestCase):
    @patch.object(service.query, "get_penandatangan", return_value=[{"id_pegawai": 3, "jabatan": "Sekretaris Desa"}])
    def test_atas_nama_bukan_kades(self, _):
        self.assertEqual(service._penandatangan(3), (3, 1))

    @patch.object(service.query, "get_penandatangan", return_value=[])
    def test_bukan_penandatangan(self, _):
        with self.assertRaises(ValidationError):
            service._penandatangan(9)


if __name__ == "__main__":
    unittest.main()


class NomorTest(unittest.TestCase):
    def test_format_nomor(self):
        self.assertEqual(service.format_nomor("{klasifikasi}/{urut}/{kode_desa}/{tahun}", "148.1", 100, "KRB", 2026),
                         "148.1/100/KRB/2026")
