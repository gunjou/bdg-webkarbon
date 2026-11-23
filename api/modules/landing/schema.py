# api/modules/landing/schema.py
from flask_restx import fields, reqparse
from werkzeug.datastructures import FileStorage

from api.shared.docs import audit_fields
from . import ns

_s, _i = fields.String, fields.Integer
_gambar = dict(example="landing/0123456789abcdef0123456789abcdef.jpg",
               description="Path dari POST /landing/gambar; null = tanpa gambar")

konten_model = ns.model("LandingKonten", {
    "hero": fields.Raw(example={"badge": "Selamat Datang", "judul": "Desa", "judul_sorot": "Karang Bongkot",
                                "subjudul": "...", "lokasi": "Kec. Labuapi", "gambar": None}),
    "sekilas": fields.Raw(example={"judul": "Mengenal Desa", "isi": "...", "poin": ["..."], "gambar": None}),
    "sejarah": fields.Raw(example={"paragraf": ["..."], "gambar": None}),
    "visi": _s(example="Menuju Desa Karang Bongkot yang ROMANTIS"),
    "visi_kata": fields.List(_s, example=["Religius", "Optimis"]),
    "misi": fields.List(_s),
    "batas": fields.Raw(example=[{"sisi": "Utara", "nama": "Desa Terong Tawah"}]),
    "dusun": fields.List(_s),
    "statistik": fields.Raw(example=[{"ikon": "PENDUDUK", "nilai": "8.898", "label": "Penduduk"}],
                            description="ikon = kode konstanta frontend"),
    "kontak": fields.Raw(example={"alamat": "...", "email": "...", "jam": "...", "koordinat": "-8.63,116.09"}),
    "sosmed": fields.Raw(example={"facebook": "", "instagram": "", "youtube": ""}),
})

gambar_out = ns.model("LandingGambar", {"path": _s(**_gambar)})

perangkat_input = ns.model("PerangkatDesaInput", {
    "nama": _s(required=True, max_length=150, example="Muldan, S.H"),
    "jabatan": _s(required=True, max_length=150, example="Kepala Desa"),
    "foto_path": _s(**_gambar),
    "urutan": _i(example=1, description="Kecil tampil dulu"),
})
perangkat_out = ns.clone("PerangkatDesa", perangkat_input, {"id_perangkat_desa": _i(example=1), **audit_fields()})

potensi_input = ns.model("PotensiInput", {
    "judul": _s(required=True, max_length=150, example="Pertanian"),
    "deskripsi": _s(required=True, max_length=2000, example="Areal persawahan ± 45 Ha"),
    "kategori": _s(required=True, example="PERTANIAN", description="Kode konstanta frontend (A-Z0-9_)"),
    "foto_path": _s(**_gambar),
    "urutan": _i(example=1),
})
potensi_out = ns.clone("Potensi", potensi_input, {"id_potensi": _i(example=1), **audit_fields()})

berita_input = ns.model("BeritaInput", {
    "judul": _s(required=True, max_length=200, example="Jalan Sehat HUT RI ke-81"),
    "slug": _s(example="jalan-sehat-hut-ri-81", description="Kosong = dibuat dari judul; bentrok → ditambah -2, -3"),
    "ringkasan": _s(required=True, max_length=500),
    "isi": _s(required=True, description="HTML artikel (disanitasi: p, h2-h4, list, a, img, blockquote, ...)"),
    "sampul_path": _s(**_gambar),
    "status": _s(enum=["draft", "terbit"], example="draft"),
    "tanggal_terbit": fields.Date(example="2026-11-23", description="Kosong saat terbit = hari ini; masa depan = terjadwal"),
})
berita_ringkas_out = ns.model("BeritaRingkas", {
    "id_berita": _i(example=1),
    "judul": _s(), "slug": _s(), "ringkasan": _s(), "sampul_path": _s(**_gambar),
    "status": _s(enum=["draft", "terbit"]), "tanggal_terbit": fields.Date(),
    "created_at": fields.DateTime(), "updated_at": fields.DateTime(),
})
berita_out = ns.clone("Berita", berita_ringkas_out, {"isi": _s(), **audit_fields()})

publik_out = ns.model("LandingPublik", {
    "konten": fields.Nested(konten_model),
    "perangkat": fields.List(fields.Nested(perangkat_out)),
    "potensi": fields.List(fields.Nested(potensi_out)),
})

gambar_parser = reqparse.RequestParser()
gambar_parser.add_argument("gambar", type=FileStorage, location="files", required=True, help="png/jpg/webp")

berita_parser = reqparse.RequestParser()
berita_parser.add_argument("status", choices=("draft", "terbit"), location="args")
berita_parser.add_argument("q", location="args", help="cari judul")
berita_parser.add_argument("limit", type=int, default=10, location="args", help="maks 50")
berita_parser.add_argument("offset", type=int, default=0, location="args")

publik_berita_parser = reqparse.RequestParser()
publik_berita_parser.add_argument("q", location="args", help="cari judul")
publik_berita_parser.add_argument("limit", type=int, default=10, location="args", help="maks 50")
publik_berita_parser.add_argument("offset", type=int, default=0, location="args")
