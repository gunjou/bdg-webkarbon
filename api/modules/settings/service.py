# api/modules/settings/service.py
"""Pengaturan desa & persuratan. Daftar key valid = REGISTRY (key lain ditolak).
Nilai = baris tabel settings jika ada, selain itu default di REGISTRY.
Key presensi (ABSEN_MASUK_BUKA_MENIT, ...) tetap dikelola modul presensi."""
import io
import os
import re

from PIL import Image, UnidentifiedImageError

from api.core.storage import delete_file, full_path, save_file
from api.shared.exceptions import ValidationError
from . import query

NOMOR_TOKENS = {"klasifikasi", "urut", "kode_desa", "tahun"}
LOGO_MAX_PX = 600


def _text(required=False, max_len=255):
    def check(v):
        v = str(v or "").strip()
        if required and not v:
            raise ValueError("Wajib diisi")
        if len(v) > max_len:
            raise ValueError(f"Maks {max_len} karakter")
        return v
    return check


def _choice(*opts):
    def check(v):
        v = str(v or "").strip().upper()
        if v not in opts:
            raise ValueError("Pilihan: " + " / ".join(opts))
        return v
    return check


def _kode_desa(v):
    v = str(v or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9.\-]{1,20}", v):
        raise ValueError("Huruf/angka/titik/strip, maks 20")
    return v


def _format_nomor(v):
    v = str(v or "").strip()
    tokens = set(re.findall(r"\{(\w+)\}", v))
    if "urut" not in tokens:
        raise ValueError("Wajib memuat {urut}")
    if tokens - NOMOR_TOKENS:
        raise ValueError("Token tidak dikenal: " + ", ".join(sorted(tokens - NOMOR_TOKENS)))
    if len(v) > 100:
        raise ValueError("Maks 100 karakter")
    return v


# key: (default, validator, deskripsi). validator None = tidak bisa diubah lewat PUT
REGISTRY = {
    "desa.nama": ("Karang Bongkot", _text(True, 100), "Nama desa (kop & tanda tangan)"),
    "desa.kecamatan": ("Labuapi", _text(True, 100), "Nama kecamatan"),
    "desa.kabupaten": ("Lombok Barat", _text(True, 100), "Nama kabupaten"),
    "desa.alamat": ("Jln. Gunung Pengsong No. 1 Desa Karang Bongkot Kec. Labuapi Kode Pos 83361", _text(),
                    "Alamat kantor desa (kop)"),
    "desa.email": ("karangbongkot16@gmail.com", _text(max_len=150), "Email desa (kop)"),
    "desa.website": ("karangbongkot.com", _text(max_len=150), "Website desa (kop)"),
    "desa.logo_path": (None, None, "Path logo kanan kop (upload); kosong = logo desa bawaan"),
    "desa.logo_kiri_path": (None, None, "Path logo kiri kop (upload); kosong = logo Kabupaten Lombok Barat bawaan"),
    "surat.kode_desa": ("KRB", _kode_desa, "Kode desa di nomor surat"),
    "surat.format_nomor": ("{klasifikasi}/{urut}/{kode_desa}/{tahun}", _format_nomor, "Format nomor surat"),
    "surat.cakupan_nomor": ("GLOBAL", _choice("GLOBAL", "PER_JENIS"), "Nomor urut global atau per jenis surat"),
    "surat.ukuran_kertas": ("F4", _choice("F4", "A4"), "Ukuran kertas PDF surat"),
}
DESCRIPTIONS = {k: d for k, (_, _, d) in REGISTRY.items()}


def get_all():
    """Dipakai juga modul lain (render surat, nomor)."""
    return {**{k: d for k, (d, _, _) in REGISTRY.items()}, **query.get_values(REGISTRY)}


def update(data, id_user):
    data = data or {}
    unknown = [k for k in data if k not in REGISTRY or REGISTRY[k][1] is None]
    if unknown:
        raise ValidationError("Key pengaturan tidak dikenal / tidak bisa diubah", {k: "Tidak dikenal" for k in unknown})
    values, errors = {}, {}
    for k, v in data.items():
        try:
            values[k] = REGISTRY[k][1](v)
        except ValueError as e:
            errors[k] = str(e)
    if errors:
        raise ValidationError("Pengaturan tidak valid", errors)
    if values:
        query.upsert(values, DESCRIPTIONS, id_user)
    return get_all()


ASSETS = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
# posisi -> (key settings, file bawaan, mimetype bawaan)
LOGO = {"kanan": ("desa.logo_path", os.path.join(ASSETS, "logo-desa.png"), "image/png"),
        "kiri": ("desa.logo_kiri_path", os.path.join(ASSETS, "logo-kabupaten.svg"), "image/svg+xml")}


def _logo_key(posisi):
    if posisi not in LOGO:
        raise ValidationError("Posisi logo tidak valid", {"posisi": "kiri / kanan"})
    return LOGO[posisi][0]


def set_logo(data, id_user, posisi="kanan"):
    key = _logo_key(posisi)
    if not data:
        raise ValidationError("Logo wajib diisi", {"logo": "required"})
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise ValidationError("File bukan gambar", {"logo": "Harus png/jpg"})
    img.thumbnail((LOGO_MAX_PX, LOGO_MAX_PX))
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, "PNG")  # PNG agar transparansi logo tetap
    old = get_all()[key]
    path = save_file(buf.getvalue(), "settings", "png")
    try:
        query.upsert({key: path}, DESCRIPTIONS, id_user)
    except Exception:
        delete_file(path)
        raise
    delete_file(old)
    return get_all()


def get_logo_file(posisi="kanan"):
    """(path, mimetype) logo kop: upload bila ada, selain itu bawaan (kanan = logo desa, kiri = logo kabupaten)."""
    key = _logo_key(posisi)
    rel = get_all()[key]
    full = rel and full_path(rel)
    if full and os.path.exists(full):
        return full, "image/png"
    return os.path.abspath(LOGO[posisi][1]), LOGO[posisi][2]


def get_logo_bytes(posisi="kanan"):
    """Isi file logo upload untuk kop surat; None bila belum di-upload / file hilang."""
    rel = get_all()[_logo_key(posisi)]
    full = rel and full_path(rel)
    if not full:
        return None
    try:
        with open(full, "rb") as f:
            return f.read()
    except OSError:
        return None
