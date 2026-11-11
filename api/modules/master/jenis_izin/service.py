# api/modules/master/jenis_izin/service.py
from api.shared.exceptions import NotFoundError, ValidationError
from . import query


def _clean(data, id_jenis_izin=None):
    code = data["code"].strip().upper()
    name = data["name"].strip()
    if not code or not name:
        raise ValidationError("Kode & nama wajib diisi", {"code": "required", "name": "required"})
    dup = query.find_by_code(code, id_jenis_izin)
    if dup:
        hint = "" if dup["is_active"] == 1 else " (nonaktif, aktifkan kembali saja)"
        raise ValidationError("Kode jenis izin sudah dipakai" + hint, {"code": "Sudah dipakai"})
    return {
        "code": code,
        "name": name,
        "butuh_lampiran": 1 if data.get("butuh_lampiran") == 1 else 0,
        "dihitung_hadir": 1 if data.get("dihitung_hadir") == 1 else 0,
    }


def list_all():
    return query.get_all()


def get(id_jenis_izin):
    row = query.get_by_id(id_jenis_izin)
    if not row:
        raise NotFoundError("Jenis izin tidak ditemukan")
    return row


def create(data, id_user):
    return get(query.insert(_clean(data), id_user))


def update(id_jenis_izin, data, id_user):
    get(id_jenis_izin)
    query.update(id_jenis_izin, _clean(data, id_jenis_izin), id_user)
    return get(id_jenis_izin)


def deactivate(id_jenis_izin, id_user):
    get(id_jenis_izin)
    pending = query.count_pending_perizinan(id_jenis_izin)
    if pending:
        raise ValidationError(f"Masih ada {pending} pengajuan izin berstatus diajukan dengan jenis ini")
    query.set_active(id_jenis_izin, 0, id_user)


def activate(id_jenis_izin, id_user):
    get(id_jenis_izin)
    query.set_active(id_jenis_izin, 1, id_user)
    return get(id_jenis_izin)
