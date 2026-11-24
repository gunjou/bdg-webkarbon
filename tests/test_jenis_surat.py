"""Validasi skema_form & template jenis surat + helper template. Tanpa DB."""
import unittest

from jinja2.exceptions import SecurityError

from api.modules.jenis_surat import service
from api.shared.exceptions import ValidationError
from api.utils.template import make_env, terbilang, tgl_indo

SKEMA = {"sections": [
    {"key": "pemohon", "label": "Pemohon", "type": "penduduk", "tampilkan": ["nama", "ttl"]},
    {"key": "lain", "label": "Lainnya", "type": "fields", "fields": [
        {"key": "keperluan", "label": "Keperluan", "type": "text", "required": 1, "register": True},
        {"key": "harga", "label": "Harga", "type": "rupiah"},
        {"key": "dusun", "label": "Dusun", "type": "select", "options_group": "dusun"}]},
    {"key": "batas", "label": "Batas", "type": "daftar", "columns": [{"key": "arah", "label": "Arah", "type": "text"}]},
]}


class SkemaTest(unittest.TestCase):
    def test_valid_dinormalisasi(self):
        s = service.validate_skema(SKEMA)
        f = s["sections"][1]["fields"]
        self.assertEqual((f[0]["required"], f[2]["options_group"]), (True, "DUSUN"))

    def assertErr(self, skema, path):
        with self.assertRaises(ValidationError) as e:
            service.validate_skema(skema)
        self.assertIn(path, e.exception.errors)

    def test_key_ganda(self):
        s = {"sections": [SKEMA["sections"][0], {"key": "pemohon", "label": "X", "type": "teks_bebas"}]}
        self.assertErr(s, "skema_form.sections[1].key")

    def test_tanpa_penduduk(self):
        self.assertErr({"sections": [SKEMA["sections"][1]]}, "skema_form.sections")

    def test_dinas_boleh_tanpa_penduduk(self):
        s = service.validate_skema({"layout": "dinas", "sections": [SKEMA["sections"][1]]})
        self.assertEqual(s["layout"], "dinas")
        self.assertEqual(service.pemohon(s, {"kepada": "Camat"}), (None, {"nama": "Camat"}))
        self.assertErr({"layout": "x", "sections": SKEMA["sections"]}, "skema_form.layout")

    def test_select_tanpa_opsi_dan_key_cadangan(self):
        s = {"sections": [SKEMA["sections"][0], {"key": "x", "label": "X", "type": "fields", "fields": [
            {"key": "desa", "label": "A", "type": "text"}, {"key": "b", "label": "B", "type": "select"}]}]}
        self.assertErr(s, "skema_form.sections[1].fields[0].key")
        self.assertErr(s, "skema_form.sections[1].fields[1].options")


class TemplateTest(unittest.TestCase):
    skema = service.validate_skema(SKEMA)

    def test_default_dan_placeholder_valid(self):
        html = service.clean_template("", self.skema)
        self.assertIn("biodata(pemohon)", html)
        for p in service.placeholders(self.skema):
            service.clean_template(f"<p>{p['token']}</p>", self.skema)

    def test_variabel_asing_ditolak(self):
        with self.assertRaises(ValidationError):
            service.clean_template("<p>{{ tidak_ada }}</p>", self.skema)

    def test_blok_dan_sintaks_ditolak(self):
        for bad in ("{% for x in batas %}{% endfor %}", "{{ keperluan ", "{{ keperluan | filter_asing }}"):
            with self.assertRaises(ValidationError):
                service.clean_template(bad, self.skema)

    def test_html_dibersihkan(self):
        html = service.clean_template('<p onclick="x">A {{ keperluan }}<script>1</script></p>', self.skema)
        self.assertEqual(html, "<p>A {{ keperluan }}</p>")

    def test_sandbox_blok_ssti(self):
        with self.assertRaises(SecurityError):
            make_env().from_string("{{ ''.__class__.__mro__[1].__subclasses__() }}").render()


class HelperTest(unittest.TestCase):
    def test_tgl_terbilang(self):
        self.assertEqual(tgl_indo("1998-11-03"), "3 November 1998")
        self.assertEqual(terbilang(50000000, "rupiah"), "lima puluh juta rupiah")
        self.assertEqual(terbilang(1011), "seribu sebelas")
        self.assertEqual(terbilang(0), "nol")


if __name__ == "__main__":
    unittest.main()


class RenderHtmlTest(unittest.TestCase):
    """Render HTML (tanpa PDF/pango)."""
    def test_render_lengkap(self):
        from api.modules.jenis_surat import render
        skema = service.validate_skema(SKEMA)
        redaksi = service.clean_template(
            "<p>{{ biodata(pemohon) }}</p><p>{{ keperluan }} {{ harga }} ({{ terbilang(harga, 'rupiah') }}) "
            "{{ dusun }} {{ pemohon.ttl }}</p>{{ tabel(batas) }}", skema)
        data = {"pemohon": {"nama": "<b>Gugun</b>", "tempat_lahir": "Mataram", "tanggal_lahir": "1998-11-03"},
                "keperluan": "Melamar kerja", "harga": "50000000", "dusun": "DK", "batas": [{"arah": "Utara"}]}
        settings = {"desa.nama": "Karang Bongkot", "desa.kecamatan": "Labuapi", "desa.kabupaten": "Lombok Barat",
                    "surat.ukuran_kertas": "F4"}
        html = render.render_html(judul="SK", redaksi=redaksi, skema=skema, data=data, labels={"DUSUN": {"DK": "Dasan Kebon"}},
                                  settings=settings, nomor="148.1/1/KRB/2026", tanggal="2026-11-16",
                                  penandatangan={"nama": "Budi", "jabatan": "Sekretaris Desa", "atas_nama": 1},
                                  watermark="DRAF")
        for teks in ("&lt;b&gt;Gugun&lt;/b&gt;", "Mataram, 3 November 1998", "Rp 50.000.000",
                     "lima puluh juta rupiah", "Dasan Kebon", "<td>Utara</td>", "a.n. Kepala Desa Karang Bongkot",
                     "Sekretaris Desa", "16 November 2026", "215mm 330mm", "DRAF"):
            self.assertIn(teks, html)


class SeedTest(unittest.TestCase):
    def test_seed_valid_dan_dinas_render(self):
        import sys
        from pathlib import Path
        from api.modules.jenis_surat import render
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from seed_jenis_surat import JENIS
        settings = {"desa.nama": "Karang Bongkot", "desa.kecamatan": "Labuapi", "desa.kabupaten": "Lombok Barat"}
        for code, name, _, skema, redaksi, _ in JENIS:
            sk = service.validate_skema(skema)
            data = {**service.sample_data(sk), "kepada": "Camat", "tembusan": "Arsip\nBPD"}
            html = render.render_html(judul=name, redaksi=service.clean_template(redaksi, sk), skema=sk, data=data,
                                      labels={}, settings=settings, penandatangan={"nama": "Budi", "jabatan": "Kepala Desa"})
            self.assertIn("Kepala Desa Karang Bongkot", html, code)
            if sk["layout"] == "dinas":
                self.assertIn("Yth. Camat", html)
                self.assertIn("<li>BPD</li>", html)
                self.assertNotIn('class="judul"', html)
            else:
                self.assertIn("Budi", html.split('class="ttd"')[0], code)  # {{ ttd.nama }} di redaksi
