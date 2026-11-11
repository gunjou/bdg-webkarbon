# api/modules/pegawai/service.py
import os

from api.core import storage
from api.modules.master.jabatan import service as jabatan_service
from api.modules.master.jadwal_kerja import service as jadwal_kerja_service
from api.modules.users import service as users_service
from api.shared.exceptions import NotFoundError, ValidationError
from api.utils.face import FaceError, process_face_photo
from . import query

DEFAULT_JADWAL_KERJA = 1

# field -> service master yang memvalidasi referensinya
_REFS = {
    "id_jabatan": jabatan_service,
    "id_jadwal_kerja": jadwal_kerja_service,
}


def _opt_str(value):
    return (value or "").strip() or None


def _check_refs(clean, current=None):
    """Referensi master harus ada & aktif; nilai yang tidak berubah dari data lama boleh tetap (walau nonaktif)."""
    errors = {}
    for field, svc in _REFS.items():
        value = clean[field]
        if value is None or (current and current[field] == value):
            continue
        try:
            if svc.get(value)["is_active"] != 1:
                errors[field] = "Tidak aktif"
        except NotFoundError:
            errors[field] = "Tidak ditemukan"
    if errors:
        raise ValidationError("Data referensi tidak valid", errors)


def _clean(data, current=None):
    clean = {
        "full_name": (data.get("full_name") or "").strip(),
        "id_jabatan": data["id_jabatan"],
        "id_jadwal_kerja": data.get("id_jadwal_kerja") or DEFAULT_JADWAL_KERJA,
        "nip": _opt_str(data.get("nip")),
        "phone": _opt_str(data.get("phone")),
    }
    if not clean["full_name"]:
        raise ValidationError("Nama pegawai wajib diisi", {"full_name": "required"})
    if clean["nip"] and len(clean["nip"]) > 30:
        raise ValidationError("NIP maksimal 30 karakter", {"nip": "max 30"})
    if clean["phone"] and len(clean["phone"]) > 20:
        raise ValidationError("No. HP maksimal 20 karakter", {"phone": "max 20"})
    if clean["nip"]:
        dup = query.find_by_nip(clean["nip"], current and current["id_pegawai"])
        if dup:
            raise ValidationError(f"NIP sudah dipakai {dup['full_name']}", {"nip": "Sudah dipakai"})
    _check_refs(clean, current)
    return clean


def _check_user_fields(data, is_new):
    """Validasi bentuk field user dari form (multipart tidak divalidasi model restx)."""
    errors = {}
    username = (data.get("username") or "").strip()
    if not 3 <= len(username) <= 50:
        errors["username"] = "3-50 karakter"
    if data.get("email") and len(data["email"].strip()) > 150:
        errors["email"] = "max 150"
    if is_new and len(data.get("password") or "") < 8:
        errors["password"] = "Minimal 8 karakter"
    if errors:
        raise ValidationError("Data akun tidak valid", errors)


def _process_foto(foto):
    """foto = bytes atau None. Kembalikan (jpeg_bytes, embedding) atau (None, None)."""
    if not foto:
        return None, None
    try:
        return process_face_photo(foto)
    except FaceError as e:
        raise ValidationError(str(e), {"foto": str(e)})


def list_all():
    return query.get_all()


def get(id_pegawai):
    row = query.get_by_id(id_pegawai)
    if not row:
        raise NotFoundError("Pegawai tidak ditemukan")
    return row


def create(data, foto, actor, actor_permissions):
    """Buat pegawai + akun user (+ foto wajah opsional) sekaligus."""
    pegawai = _clean(data)
    _check_user_fields(data, is_new=True)
    user, id_roles = users_service.prepare_new(data, actor_permissions)
    jpeg, embedding = _process_foto(foto)

    pegawai["photo_path"] = storage.save_file(jpeg, "pegawai", "jpg") if jpeg else None
    pegawai["embedding"] = embedding
    try:
        id_pegawai = query.insert(pegawai, user, id_roles, actor)
    except Exception:
        storage.delete_file(pegawai["photo_path"])  # DB gagal -> jangan tinggalkan file yatim
        raise
    return get(id_pegawai)


def update(id_pegawai, data, actor, actor_permissions):
    current = get(id_pegawai)
    if current["id_user"] is None:
        raise ValidationError("Pegawai ini belum punya akun user")
    pegawai = _clean(data, current)
    _check_user_fields(data, is_new=False)
    data = {k: v for k, v in data.items() if k != "password"}  # password hanya lewat set_password
    user, id_roles = users_service.prepare_update(current["id_user"], data, actor_permissions)
    query.update(id_pegawai, pegawai, current["id_user"], user, id_roles, actor)
    return get(id_pegawai)


def set_foto(id_pegawai, foto, actor):
    current = get(id_pegawai)
    jpeg, embedding = _process_foto(foto)
    if not jpeg:
        raise ValidationError("Foto wajib diisi", {"foto": "required"})
    path = storage.save_file(jpeg, "pegawai", "jpg")
    try:
        query.set_photo(id_pegawai, path, embedding, actor)
    except Exception:
        storage.delete_file(path)
        raise
    storage.delete_file(current["photo_path"])
    return get(id_pegawai)


def get_foto_path(id_pegawai):
    row = get(id_pegawai)
    full = row["photo_path"] and storage.full_path(row["photo_path"])
    if not full or not os.path.exists(full):
        raise NotFoundError("Foto pegawai belum ada")
    return full


def deactivate(id_pegawai, actor, actor_permissions):
    current = get(id_pegawai)
    if current["id_user"] is not None:
        if current["id_user"] == actor:
            raise ValidationError("Tidak boleh menonaktifkan akun sendiri")
        users_service.guard_target(current["id_user"], actor_permissions)
    query.set_active(id_pegawai, 0, actor)


def activate(id_pegawai, actor, actor_permissions):
    current = get(id_pegawai)
    if current["id_user"] is not None:
        users_service.guard_target(current["id_user"], actor_permissions)
    query.set_active(id_pegawai, 1, actor)
    return get(id_pegawai)


def set_password(id_pegawai, password, actor, actor_permissions):
    current = get(id_pegawai)
    if current["id_user"] is None:
        raise ValidationError("Pegawai ini belum punya akun user")
    users_service.set_password(current["id_user"], password, actor, actor_permissions)
