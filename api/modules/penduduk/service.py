# api/modules/penduduk/service.py
"""Data induk warga. Hanya diisi dari menu Penduduk (pemohon surat yang diisi manual TIDAK masuk ke sini).
Kolom agama/pekerjaan/status_perkawinan/kewarganegaraan/dusun berisi code ref_options; kode baru/yang diganti harus aktif,
kode lama yang tidak diganti tetap diterima walau opsinya sudah nonaktif.
is_active = 0 untuk warga pindah/meninggal; tidak pernah dihapus."""
import re
from datetime import date

from api.modules.master.ref_options import service as ref_options_service
from api.shared.exceptions import NotFoundError, ValidationError
from api.utils.datetime import get_wita
from . import query

REF_FIELDS = {
    "agama": "AGAMA",
    "pekerjaan": "PEKERJAAN",
    "status_perkawinan": "STATUS_PERKAWINAN",
    "kewarganegaraan": "KEWARGANEGARAAN",
    "dusun": "DUSUN",
}
MAX_LIMIT = 200


def _opt(data, key, upper=False):
    v = str(data.get(key) or "").strip()
    return (v.upper() if upper else v) or None


def _clean(data, current=None):
    id_penduduk = current["id_penduduk"] if current else None
    out = {c: _opt(data, c) for c in query.COLUMNS}
    if not out["full_name"]:
        raise ValidationError("Nama wajib diisi", {"full_name": "required"})
    for k in REF_FIELDS:
        out[k] = _opt(data, k, upper=True)
    out["kewarganegaraan"] = out["kewarganegaraan"] or "WNI"
    out["jenis_kelamin"] = _opt(data, "jenis_kelamin", upper=True)
    if out["jenis_kelamin"] not in (None, "L", "P"):
        raise ValidationError("Jenis kelamin tidak valid", {"jenis_kelamin": "L / P"})
    for k in ("nik", "no_kk"):
        if out[k] and not re.fullmatch(r"[0-9]{16}", out[k]):
            raise ValidationError("Harus 16 digit angka", {k: "16 digit"})
    for k in ("rt", "rw"):
        if out[k]:
            if not out[k].isdigit() or len(out[k]) > 3:
                raise ValidationError("RT/RW harus angka", {k: "Maks 3 digit"})
            out[k] = out[k].zfill(3)
    if out["tanggal_lahir"]:
        try:
            out["tanggal_lahir"] = date.fromisoformat(out["tanggal_lahir"])
        except ValueError:
            raise ValidationError("Tanggal lahir tidak valid", {"tanggal_lahir": "Format YYYY-MM-DD"})
        if out["tanggal_lahir"] > get_wita().date():
            raise ValidationError("Tanggal lahir di masa depan", {"tanggal_lahir": "Tidak valid"})
    # kode lama yang tidak diganti tetap boleh disimpan walau opsinya sudah dinonaktifkan
    changed = {k: g for k, g in REF_FIELDS.items() if not current or out[k] != current[k]}
    ref_options_service.validate_codes({k: (g, out[k]) for k, g in changed.items()})
    if out["nik"]:
        dup = query.find_by_nik(out["nik"], id_penduduk)
        if dup:
            hint = "" if dup["is_active"] == 1 else ", nonaktif — aktifkan kembali saja"
            raise ValidationError(f"NIK sudah terdaftar ({dup['full_name']}{hint})", {"nik": "Sudah terdaftar"})
    return out


def search(args):
    q = (args.get("q") or "").strip()
    digits = q.isdigit()
    return query.search({
        "nomor": q if digits else None,
        "nama": q.lower() if q and not digits else None,
        "dusun": (args.get("dusun") or "").strip().upper() or None,
        "include_inactive": 1 if args.get("include_inactive") == 1 else 0,
        "limit": min(max(args.get("limit") or 50, 1), MAX_LIMIT),
        "offset": max(args.get("offset") or 0, 0),
    })


def get(id_penduduk):
    row = query.get_by_id(id_penduduk)
    if not row:
        raise NotFoundError("Penduduk tidak ditemukan")
    return row


def create(data, id_user):
    return get(query.insert(_clean(data), id_user))


def update(id_penduduk, data, id_user):
    current = get(id_penduduk)
    query.update(id_penduduk, _clean(data, current), id_user)
    return get(id_penduduk)


def deactivate(id_penduduk, id_user):
    get(id_penduduk)
    query.set_active(id_penduduk, 0, id_user)


def activate(id_penduduk, id_user):
    row = get(id_penduduk)
    if row["nik"]:
        dup = query.find_by_nik(row["nik"], id_penduduk)
        if dup:
            raise ValidationError(f"NIK sudah dipakai {dup['full_name']}", {"nik": "Sudah terdaftar"})
    query.set_active(id_penduduk, 1, id_user)
    return get(id_penduduk)
