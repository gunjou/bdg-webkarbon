"""Konten website desa: validasi, sanitasi artikel, batas file publik. DB di-mock."""
import io
import unittest
from unittest.mock import patch

from PIL import Image

from api.modules.landing import service
from api.shared.exceptions import NotFoundError, ValidationError

GAMBAR = "landing/" + "a" * 32 + ".jpg"


class SanitasiTest(unittest.TestCase):
    def test_artikel(self):
        out = service.sanitize_artikel('<h2>J</h2><script>x()</script><p onclick="x" style="a">t</p>'
                                       '<a href="javascript:x">l</a><img src="https://a/b.jpg" onerror="x">')
        self.assertNotIn("script", out)
        self.assertNotIn("onclick", out)
        self.assertNotIn("javascript", out)
        self.assertNotIn("onerror", out)
        self.assertIn("<h2>J</h2>", out)
        self.assertIn('src="https://a/b.jpg"', out)

    def test_slugify(self):
        self.assertEqual(service.slugify("Jalan Sehat HUT RI ke-81!"), "jalan-sehat-hut-ri-ke-81")


@patch.object(service.query, "save_konten")
@patch.object(service.query, "get_konten", return_value={"visi": "lama", "misi": ["a"]})
class KontenTest(unittest.TestCase):
    def test_merge_per_bagian(self, _g, save):
        self.assertEqual(service.update_konten({"visi": "baru"}, 1), {"visi": "baru", "misi": ["a"]})
        save.assert_called_once()

    def test_tolak(self, _g, save):
        for bad in ({}, {"foo": 1}, {"hero": {"gambar": "../pegawai/x.jpg"}},
                    {"sekilas": {"gambar": "presensi/" + "a" * 32 + ".jpg"}}):
            with self.assertRaises(ValidationError):
                service.update_konten(bad, 1)
        save.assert_not_called()

    def test_gambar_valid(self, _g, save):
        service.update_konten({"hero": {"gambar": GAMBAR}}, 1)
        save.assert_called_once()


class FileTest(unittest.TestCase):
    def test_file_publik_hanya_landing(self):
        for bad in ("pegawai/" + "a" * 32 + ".jpg", "landing/../pegawai/x.jpg", "landing/x.jpg", ""):
            with self.assertRaises(NotFoundError):
                service.file_publik(bad)

    @patch.object(service, "save_file", return_value=GAMBAR)
    def test_upload_png_transparan(self, save):
        buf = io.BytesIO()
        Image.new("RGBA", (3000, 1000), (0, 0, 0, 0)).save(buf, "PNG")
        self.assertEqual(service.upload_gambar(buf.getvalue()), {"path": GAMBAR})
        img = Image.open(io.BytesIO(save.call_args.args[0]))
        self.assertEqual((img.format, img.size), ("JPEG", (1920, 640)))
        with self.assertRaises(ValidationError):
            service.upload_gambar(b"bukan")


@patch.object(service.query, "slug_dipakai", side_effect=lambda s, _id=None: s == "judul")
class BeritaTest(unittest.TestCase):
    def test_clean(self, _):
        b = service._clean_berita({"judul": "Judul", "ringkasan": "r", "isi": "<p>x</p>", "status": "terbit"})
        self.assertEqual(b["slug"], "judul-2")
        self.assertIsNotNone(b["tanggal_terbit"])
        d = service._clean_berita({"judul": "Lain", "ringkasan": "r", "isi": "<p>x</p>"})
        self.assertEqual((d["status"], d["tanggal_terbit"]), ("draft", None))

    def test_tolak(self, _):
        base = {"judul": "J", "ringkasan": "r", "isi": "<p>x</p>"}
        for bad in ({**base, "isi": "<p> </p><script>a</script>"}, {**base, "status": "hapus"},
                    {**base, "sampul_path": "pegawai/x.jpg"}, {**base, "judul": ""}):
            with self.assertRaises(ValidationError):
                service._clean_berita(bad)


class PotensiTest(unittest.TestCase):
    def test_kategori(self):
        self.assertEqual(service._clean_potensi({"judul": "a", "deskripsi": "b", "kategori": " perikanan "})["kategori"],
                         "PERIKANAN")
        with self.assertRaises(ValidationError):
            service._clean_potensi({"judul": "a", "deskripsi": "b", "kategori": "ikan laut!"})


class SitemapTest(unittest.TestCase):
    @patch.object(service.settings_service, "get_all", return_value={"desa.website": "https://karangbongkot.com/"})
    @patch.object(service.query, "berita_sitemap", return_value=[
        {"slug": "a&b", "tanggal_terbit": __import__("datetime").date(2026, 8, 11), "updated_at": None}])
    def test_isi(self, *_):
        xml = service.publik_sitemap()
        self.assertIn("<loc>https://karangbongkot.com/profile</loc>", xml)
        self.assertIn("<loc>https://karangbongkot.com/berita/a%26b</loc><lastmod>2026-08-11</lastmod>", xml)
