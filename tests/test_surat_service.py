"""Alur surat: terbit (+ rollback), perbaikan, arsip, batal, pengganti. DB & render di-mock."""
import unittest
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

from api.modules.jenis_surat import service as js
from api.modules.surat import service
from api.shared.exceptions import ForbiddenError, ValidationError

SKEMA = js.validate_skema({"sections": [
    {"key": "pemohon", "label": "Pemohon", "type": "penduduk"},
    {"key": "lain", "label": "Lain", "type": "fields",
     "fields": [{"key": "keperluan", "label": "Keperluan", "type": "text", "required": True}]}]})
DATA = {"pemohon": {"nama": "GUGUN"}, "keperluan": "melamar kerja"}
TTD = [{"id_pegawai": 2, "full_name": "Kaharudin", "nip": None, "jabatan": "Sekretaris Desa"}]
CFG = {"surat.cakupan_nomor": "GLOBAL", "surat.format_nomor": "{klasifikasi}/{urut}/{kode_desa}/{tahun}",
       "surat.kode_desa": "KRB"}


def row(**kw):
    base = {"id_surat": 1, "id_jenis_surat": 1, "jenis_surat_code": "SKBM", "kode_klasifikasi": "148.1",
            "judul": "SKBM", "status": "draft", "skema_form": SKEMA, "redaksi": "<p>{{ keperluan }}</p>",
            "redaksi_diubah": 0, "data": DATA, "id_penandatangan": 2, "atas_nama": 1, "nomor_surat": None,
            "tanggal_surat": None, "pdf_path": None, "arsip_path": None, "id_penduduk": None,
            "nama_pemohon": "GUGUN", "nik_pemohon": None, "versi_template": 1}
    return {**base, **kw}


@contextmanager
def fake_begin():
    yield MagicMock()


class Base(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(service.query, "begin", side_effect=fake_begin),
            patch.object(service.query, "get_by_id", return_value=row()),
            patch.object(service.query, "get_penandatangan", return_value=TTD),
            patch.object(service.query, "next_nomor", return_value=7),
            patch.object(service.query, "nomor_exists", return_value=False),
            patch.object(service.settings_service, "get_all", return_value=dict(CFG)),
            patch.object(service.jenis_surat_service, "render_pdf", return_value=b"%PDF"),
            patch.object(js.ref_options_service, "validate_codes"),
            patch.object(service, "save_file", return_value="surat/pdf/baru.pdf"),
            patch.object(service, "delete_file"),
            patch.object(service, "get_wita", return_value=MagicMock(date=lambda: date(2026, 8, 24))),
        ]
        self.m = {p.attribute: p.start() for p in self.patches}
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def lock(self, **kw):
        return patch.object(service.query, "lock", return_value=row(**kw))


class TerbitTest(Base):
    def test_terbit_nomor_dan_snapshot(self):
        with self.lock(), patch.object(service.query, "set_terbit") as st:
            service.terbitkan(1, 9)
        r = st.call_args.args[2]
        self.assertEqual((r["nomor_surat"], r["nomor_urut"], r["tanggal_surat"], r["pdf_path"]),
                         ("148.1/7/KRB/2026", 7, date(2026, 8, 24), "surat/pdf/baru.pdf"))
        self.assertEqual(r["data_penandatangan"], {"id_pegawai": 2, "nama": "Kaharudin", "jabatan": "Sekretaris Desa",
                                                   "nip": None, "atas_nama": 1})
        self.assertEqual(self.m["next_nomor"].call_args.args[1:], ("GLOBAL", 2026))

    def test_cakupan_per_jenis(self):
        self.m["get_all"].return_value = {**CFG, "surat.cakupan_nomor": "PER_JENIS"}
        with self.lock(), patch.object(service.query, "set_terbit"):
            service.terbitkan(1, 9)
        self.assertEqual(self.m["next_nomor"].call_args.args[1], "SKBM")

    def test_render_gagal_tidak_simpan_apa_pun(self):
        self.m["render_pdf"].side_effect = RuntimeError("pango")
        with self.lock(), patch.object(service.query, "set_terbit") as st, self.assertRaises(RuntimeError):
            service.terbitkan(1, 9)
        st.assert_not_called()
        self.m["save_file"].assert_not_called()

    def test_update_gagal_hapus_pdf_baru(self):
        with self.lock(), patch.object(service.query, "set_terbit", side_effect=RuntimeError("db")), \
                self.assertRaises(RuntimeError):
            service.terbitkan(1, 9)
        self.m["delete_file"].assert_called_with("surat/pdf/baru.pdf")

    def test_ditolak(self):
        kasus = [dict(status="diterbitkan"), dict(data={"pemohon": {}}), dict(id_penandatangan=None)]
        for kw in kasus:
            with self.subTest(kw), self.lock(**kw), patch.object(service.query, "set_terbit") as st, \
                    self.assertRaises(ValidationError):
                service.terbitkan(1, 9)
            st.assert_not_called()

    def test_nomor_bentrok(self):
        self.m["nomor_exists"].return_value = True
        with self.lock(), patch.object(service.query, "set_terbit") as st, self.assertRaises(ValidationError):
            service.terbitkan(1, 9)
        st.assert_not_called()


class PerbaikiArsipBatalTest(Base):
    TERBIT = dict(status="diterbitkan", nomor_surat="148.1/7/KRB/2026", tanggal_surat=date(2026, 8, 24),
                  pdf_path="surat/pdf/lama.pdf")

    def test_perbaiki_nomor_tetap_pdf_lama_dihapus(self):
        with self.lock(**self.TERBIT), patch.object(service.query, "set_perbaikan") as sp:
            service.perbaiki(1, {"catatan": "typo", "data": DATA}, False, 9)
        self.assertEqual(self.m["render_pdf"].call_args.kwargs["nomor"], "148.1/7/KRB/2026")
        self.assertEqual(sp.call_args.args[2]["pdf_path"], "surat/pdf/baru.pdf")
        self.m["delete_file"].assert_called_with("surat/pdf/lama.pdf")

    def test_perbaiki_ditolak(self):
        with self.lock(**self.TERBIT, arsip_path="surat/arsip/a.png"), self.assertRaises(ValidationError):
            service.perbaiki(1, {"catatan": "x"}, True, 9)
        with self.lock(**self.TERBIT), self.assertRaises(ForbiddenError):
            service.perbaiki(1, {"catatan": "x", "redaksi": "<p>{{ keperluan }} baru</p>"}, False, 9)
        with self.assertRaises(ValidationError):
            service.perbaiki(1, {"catatan": " "}, True, 9)

    def test_arsip_hanya_terbit_dan_tipe_file(self):
        with self.assertRaises(ValidationError):
            service.arsipkan(1, b"bukan gambar", 9)
        with self.lock(), self.assertRaises(ValidationError):  # masih draft
            service.arsipkan(1, b"%PDF scan", 9)

    def test_batal(self):
        with self.assertRaises(ValidationError):
            service.batalkan(1, " ", 9)
        with self.lock(status="dibatalkan"), self.assertRaises(ValidationError):
            service.batalkan(1, "dobel", 9)
        with self.lock(**self.TERBIT), patch.object(service.query, "set_batal") as sb:
            service.batalkan(1, " Salah nama ", 9)
        self.assertEqual(sb.call_args.args[2], "Salah nama")

    def test_pengganti(self):
        with self.lock(status="dibatalkan"), self.assertRaises(ValidationError):  # batal saat draft (tanpa nomor)
            service.buat_pengganti(1, 9)
        batal = dict(status="dibatalkan", nomor_surat="148.1/7/KRB/2026")
        with self.lock(**batal), patch.object(service.query, "find_pengganti", return_value=5), \
                self.assertRaises(ValidationError):
            service.buat_pengganti(1, 9)
        with self.lock(**batal), patch.object(service.query, "find_pengganti", return_value=None), \
                patch.object(service.query, "insert_pengganti", return_value=2) as ins, \
                patch.object(service.query, "add_riwayat"):
            service.buat_pengganti(1, 9)
        self.assertEqual((ins.call_args.args[1]["id_surat_diganti"], ins.call_args.args[1]["data"]), (1, DATA))


class KodeJenisSuratTest(unittest.TestCase):
    @patch.object(js.query, "find_by_code", return_value=None)
    @patch.object(js.query, "count_surat", return_value=3)
    def test_kode_terkunci_bila_ada_surat(self, *_):
        with self.assertRaises(ValidationError):
            js._clean_code("SKBM2", {"id_jenis_surat": 1, "code": "SKBM"})
        self.assertEqual(js._clean_code("skbm", {"id_jenis_surat": 1, "code": "SKBM"}), "SKBM")


if __name__ == "__main__":
    unittest.main()
