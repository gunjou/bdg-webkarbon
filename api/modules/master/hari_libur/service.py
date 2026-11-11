# api/modules/master/hari_libur/service.py
from datetime import date

from api.shared.exceptions import NotFoundError, ValidationError
from . import query


def _clean(data, id_hari_libur=None):
    try:
        tanggal = date.fromisoformat(str(data["tanggal"]).strip())
    except ValueError:
        raise ValidationError("Tanggal tidak valid", {"tanggal": "Format YYYY-MM-DD"})
    name = data["name"].strip()
    if not name:
        raise ValidationError("Nama hari libur wajib diisi", {"name": "required"})
    _check_tanggal_free(tanggal, id_hari_libur)
    return {"tanggal": tanggal, "name": name, "jenis": data.get("jenis") or "nasional"}


def _check_tanggal_free(tanggal, id_hari_libur):
    dup = query.find_active_by_tanggal(tanggal, id_hari_libur)
    if dup:
        raise ValidationError(f"Tanggal {tanggal.isoformat()} sudah terdaftar sebagai {dup['name']}",
                              {"tanggal": "Sudah dipakai"})


def list_all(tahun=None):
    return query.get_all(tahun)


def get(id_hari_libur):
    row = query.get_by_id(id_hari_libur)
    if not row:
        raise NotFoundError("Hari libur tidak ditemukan")
    return row


def create(data, id_user):
    return get(query.insert(_clean(data), id_user))


def update(id_hari_libur, data, id_user):
    get(id_hari_libur)
    query.update(id_hari_libur, _clean(data, id_hari_libur), id_user)
    return get(id_hari_libur)


def deactivate(id_hari_libur, id_user):
    get(id_hari_libur)
    query.set_active(id_hari_libur, 0, id_user)


def activate(id_hari_libur, id_user):
    row = get(id_hari_libur)
    _check_tanggal_free(row["tanggal"], id_hari_libur)
    query.set_active(id_hari_libur, 1, id_user)
    return get(id_hari_libur)
