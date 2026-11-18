import unittest

from api.modules.surat.schema import surat_update


class SuratUpdateSchemaTest(unittest.TestCase):
    def valid(self, body):
        try:
            surat_update.validate(body)
            return True
        except Exception:
            return False

    def test_id_penandatangan_boleh_null_angka_atau_kosong(self):
        self.assertTrue(self.valid({"data": {}, "id_penandatangan": None}))
        self.assertTrue(self.valid({"data": {}, "id_penandatangan": 3}))
        self.assertTrue(self.valid({"data": {}}))

    def test_id_penandatangan_teks_ditolak(self):
        self.assertFalse(self.valid({"data": {}, "id_penandatangan": "x"}))


if __name__ == "__main__":
    unittest.main()
