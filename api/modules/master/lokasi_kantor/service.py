# api/modules/master/lokasi_kantor/service.py
from api.shared.exceptions import NotFoundError, ValidationError
from . import query


def _clean(data, id_lokasi_kantor=None):
    name = data["name"].strip()
    if not name:
        raise ValidationError("Nama lokasi wajib diisi", {"name": "required"})
    if query.find_active_by_name(name, id_lokasi_kantor):
        raise ValidationError("Nama lokasi sudah dipakai", {"name": "Sudah dipakai"})
    radius = data.get("radius_meter") or 100
    return {
        "name": name,
        # NUMERIC(9,6): simpan 6 angka desimal (~11 cm)
        "latitude": round(float(data["latitude"]), 6),
        "longitude": round(float(data["longitude"]), 6),
        "radius_meter": radius,
    }


def list_all():
    return query.get_all()


def get(id_lokasi_kantor):
    row = query.get_by_id(id_lokasi_kantor)
    if not row:
        raise NotFoundError("Lokasi kantor tidak ditemukan")
    return row


def create(data, id_user):
    return get(query.insert(_clean(data), id_user))


def update(id_lokasi_kantor, data, id_user):
    get(id_lokasi_kantor)
    query.update(id_lokasi_kantor, _clean(data, id_lokasi_kantor), id_user)
    return get(id_lokasi_kantor)


def deactivate(id_lokasi_kantor, id_user):
    get(id_lokasi_kantor)
    used = query.count_active_pegawai(id_lokasi_kantor)
    if used:
        raise ValidationError(f"Lokasi masih dipakai {used} pegawai aktif")
    query.set_active(id_lokasi_kantor, 0, id_user)


def activate(id_lokasi_kantor, id_user):
    row = get(id_lokasi_kantor)
    if query.find_active_by_name(row["name"], id_lokasi_kantor):
        raise ValidationError("Sudah ada lokasi aktif dengan nama yang sama")
    query.set_active(id_lokasi_kantor, 1, id_user)
    return get(id_lokasi_kantor)
