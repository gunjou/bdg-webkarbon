# api/modules/master/jabatan/service.py
from api.shared.exceptions import NotFoundError, ValidationError
from . import query


def _clean(data, id_jabatan=None):
    name = data["name"].strip()
    if not name:
        raise ValidationError("Nama jabatan wajib diisi", {"name": "required"})
    dup = query.find_by_name(name, id_jabatan)
    if dup:
        hint = "" if dup["is_active"] == 1 else " (nonaktif, aktifkan kembali saja)"
        raise ValidationError("Nama jabatan sudah dipakai" + hint, {"name": "Sudah dipakai"})
    return {"name": name, "sort_order": data.get("sort_order") or 0}


def list_all():
    return query.get_all()


def get(id_jabatan):
    row = query.get_by_id(id_jabatan)
    if not row:
        raise NotFoundError("Jabatan tidak ditemukan")
    return row


def create(data, id_user):
    return get(query.insert(_clean(data), id_user))


def update(id_jabatan, data, id_user):
    get(id_jabatan)
    query.update(id_jabatan, _clean(data, id_jabatan), id_user)
    return get(id_jabatan)


def deactivate(id_jabatan, id_user):
    get(id_jabatan)
    used = query.count_active_pegawai(id_jabatan)
    if used:
        raise ValidationError(f"Jabatan masih dipakai {used} pegawai aktif")
    query.set_active(id_jabatan, 0, id_user)


def activate(id_jabatan, id_user):
    get(id_jabatan)
    query.set_active(id_jabatan, 1, id_user)
    return get(id_jabatan)
