# api/modules/landing/service.py
"""Konten website desa (karangbongkot.com).

- Konten tunggal (hero, sekilas, sejarah, visi-misi, wilayah, dusun, statistik, kontak, sosmed) = satu JSON di
  settings key 'landing.konten'. PUT menimpa per bagian (key level atas), bagian lain tetap.
- Perangkat desa & potensi = daftar sederhana (urutan, soft delete). Kategori potensi & ikon statistik = kode
  konstanta di frontend; backend hanya cek formatnya (KODE).
- Berita: isi = HTML artikel dari editor admin, selalu disanitasi nh3 (publik merender HTML ini).
  Publik hanya melihat status 'terbit' dengan tanggal_terbit <= hari ini (WITA).
- Gambar: upload dulu (POST /landing/gambar) → path 'landing/<hex>.jpg', lalu path dipakai di konten/tabel.
  Publik mengunduh lewat /landing/publik/file/<path>, dibatasi folder landing/ saja.
"""
import io
import json
import os
import re
import unicodedata

import nh3
from PIL import Image, UnidentifiedImageError

from api.core.storage import full_path, save_file
from api.shared.exceptions import NotFoundError, ValidationError
from api.utils.datetime import get_wita
from . import query

KONTEN_KEYS = ("hero", "sekilas", "sejarah", "visi", "visi_kata", "misi", "batas", "dusun",
               "statistik", "kontak", "sosmed")
KONTEN_MAX_BYTES = 100_000
GAMBAR_MAX_PX = 1920
RE_GAMBAR = re.compile(r"landing/[0-9a-f]{32}\.jpg")
RE_KODE = re.compile(r"[A-Z0-9_]{1,30}")
LIMIT_MAX = 50

# artikel blog: tanpa style/script/iframe; link & gambar hanya http(s)
ARTIKEL_TAGS = {"p", "br", "h2", "h3", "h4", "strong", "b", "em", "i", "u", "s", "blockquote", "ul", "ol", "li",
                "a", "img", "figure", "figcaption", "hr", "code", "pre"}
ARTIKEL_ATTRS = {"a": {"href", "title", "target"}, "img": {"src", "alt", "title"}}


def sanitize_artikel(html):
    return nh3.clean(html or "", tags=ARTIKEL_TAGS, attributes=ARTIKEL_ATTRS,
                     url_schemes={"http", "https", "mailto"}, link_rel="noopener noreferrer")


def _text(data, field, required=True, max_len=255):
    v = str(data.get(field) or "").strip()
    if required and not v:
        raise ValidationError(f"{field} wajib diisi", {field: "Wajib diisi"})
    if len(v) > max_len:
        raise ValidationError(f"{field} terlalu panjang", {field: f"Maks {max_len} karakter"})
    return v


def _gambar(v, field="gambar"):
    if v in (None, ""):
        return None
    if not isinstance(v, str) or not RE_GAMBAR.fullmatch(v):
        raise ValidationError("Path gambar tidak valid", {field: "Upload lewat POST /landing/gambar"})
    return v


def _urutan(data):
    try:
        return int(data.get("urutan") or 0)
    except (TypeError, ValueError):
        raise ValidationError("Urutan harus angka", {"urutan": "Harus angka"})


# ---------------------------------------------------------------- konten
def _cek_gambar(obj):
    """Semua field bernama 'gambar' di dalam konten harus path upload landing."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "gambar":
                _gambar(v)
            else:
                _cek_gambar(v)
    elif isinstance(obj, list):
        for v in obj:
            _cek_gambar(v)


def get_konten():
    return query.get_konten() or {}


def update_konten(data, id_user):
    if not isinstance(data, dict) or not data:
        raise ValidationError("Konten wajib berupa object")
    unknown = [k for k in data if k not in KONTEN_KEYS]
    if unknown:
        raise ValidationError("Bagian konten tidak dikenal", {k: "Tidak dikenal" for k in unknown})
    _cek_gambar(data)
    final = {**get_konten(), **data}
    if len(json.dumps(final)) > KONTEN_MAX_BYTES:
        raise ValidationError("Konten terlalu besar")
    # isi teks dirender frontend sebagai teks (bukan HTML), jadi tidak perlu sanitasi di sini
    query.save_konten(final, id_user)
    return final


# ---------------------------------------------------------------- gambar
def upload_gambar(data):
    if not data:
        raise ValidationError("Gambar wajib diisi", {"gambar": "required"})
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise ValidationError("File bukan gambar", {"gambar": "Harus png/jpg/webp"})
    img.thumbnail((GAMBAR_MAX_PX, GAMBAR_MAX_PX))
    if img.mode in ("RGBA", "LA", "P"):  # transparan → latar putih
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.split()[-1])
        img = bg
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=85, optimize=True)
    # shortcut: gambar yang tidak jadi dipakai tetap tersimpan (yatim), bersihkan berkala bila folder membesar
    return {"path": save_file(buf.getvalue(), "landing", "jpg")}


def file_publik(path):
    """Path absolut file gambar landing; selain folder landing/ = 404 (foto absen dll. tidak boleh terbuka)."""
    full = RE_GAMBAR.fullmatch(path or "") and full_path(path)
    if not full or not os.path.exists(full):
        raise NotFoundError("File tidak ditemukan")
    return full


# ---------------------------------------------------------------- perangkat & potensi
def _clean_perangkat(data):
    return {"nama": _text(data, "nama", max_len=150), "jabatan": _text(data, "jabatan", max_len=150),
            "foto_path": _gambar(data.get("foto_path"), "foto_path"), "urutan": _urutan(data)}


def _clean_potensi(data):
    kategori = str(data.get("kategori") or "").strip().upper()
    if not RE_KODE.fullmatch(kategori):
        raise ValidationError("Kategori tidak valid", {"kategori": "Kode huruf besar/angka/_, maks 30"})
    return {"judul": _text(data, "judul", max_len=150), "deskripsi": _text(data, "deskripsi", max_len=2000),
            "kategori": kategori, "foto_path": _gambar(data.get("foto_path"), "foto_path"), "urutan": _urutan(data)}


CLEAN = {"perangkat": _clean_perangkat, "potensi": _clean_potensi}
LABEL = {"perangkat": "Perangkat desa", "potensi": "Potensi"}


def daftar_list(jenis):
    return query.daftar_all(jenis)


def daftar_get(jenis, id_):
    row = query.daftar_get(jenis, id_)
    if not row:
        raise NotFoundError(f"{LABEL[jenis]} tidak ditemukan")
    return row


def daftar_create(jenis, data, id_user):
    return daftar_get(jenis, query.daftar_insert(jenis, CLEAN[jenis](data or {}), id_user))


def daftar_update(jenis, id_, data, id_user):
    clean = CLEAN[jenis](data or {})
    if not query.daftar_update(jenis, id_, clean, id_user):
        raise NotFoundError(f"{LABEL[jenis]} tidak ditemukan")
    return daftar_get(jenis, id_)


def daftar_delete(jenis, id_, id_user):
    daftar_get(jenis, id_)
    query.daftar_deactivate(jenis, id_, id_user)


# ---------------------------------------------------------------- berita
def slugify(text):
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:200]


def _slug_unik(slug, exclude_id=None):
    base, n = slug, 2
    while query.slug_dipakai(slug, exclude_id):
        slug, n = f"{base}-{n}", n + 1
    return slug


def _clean_berita(data, id_berita=None):
    judul = _text(data, "judul", max_len=200)
    slug = slugify(str(data.get("slug") or "").strip() or judul)
    if not slug:
        raise ValidationError("Slug tidak valid", {"slug": "Isi huruf/angka"})
    isi = sanitize_artikel(data.get("isi"))
    if not re.sub(r"<[^>]+>", "", isi).strip() and "<img" not in isi:
        raise ValidationError("Isi berita wajib diisi", {"isi": "Wajib diisi"})
    status = str(data.get("status") or "draft").strip().lower()
    if status not in ("draft", "terbit"):
        raise ValidationError("Status tidak valid", {"status": "draft / terbit"})
    tanggal = data.get("tanggal_terbit") or None
    if status == "terbit" and not tanggal:
        tanggal = get_wita().date()
    return {"judul": judul, "slug": _slug_unik(slug, id_berita), "ringkasan": _text(data, "ringkasan", max_len=500),
            "isi": isi, "sampul_path": _gambar(data.get("sampul_path"), "sampul_path"),
            "status": status, "tanggal_terbit": tanggal}


def _paging(limit, offset):
    return max(1, min(int(limit or 10), LIMIT_MAX)), max(0, int(offset or 0))


def berita_list(status=None, q=None, limit=10, offset=0):
    limit, offset = _paging(limit, offset)
    rows, total = query.berita_list(status or None, (q or "").strip() or None, None, limit, offset)
    return rows, {"total": total, "limit": limit, "offset": offset}


def berita_get(id_berita):
    row = query.berita_get(id_berita)
    if not row:
        raise NotFoundError("Berita tidak ditemukan")
    return row


def berita_create(data, id_user):
    return berita_get(query.berita_insert(_clean_berita(data or {}), id_user))


def berita_update(id_berita, data, id_user):
    berita_get(id_berita)
    query.berita_update(id_berita, _clean_berita(data or {}, id_berita), id_user)
    return berita_get(id_berita)


def berita_delete(id_berita, id_user):
    berita_get(id_berita)
    query.berita_deactivate(id_berita, id_user)


# ---------------------------------------------------------------- publik
def publik_beranda():
    return {"konten": get_konten(), "perangkat": query.daftar_all("perangkat"), "potensi": query.daftar_all("potensi")}


def publik_berita_list(q=None, limit=10, offset=0):
    limit, offset = _paging(limit, offset)
    rows, total = query.berita_list("terbit", (q or "").strip() or None, get_wita().date(), limit, offset)
    return rows, {"total": total, "limit": limit, "offset": offset}


def publik_berita(slug):
    row = query.berita_get_publik(slug, get_wita().date())
    if not row:
        raise NotFoundError("Berita tidak ditemukan")
    return row
