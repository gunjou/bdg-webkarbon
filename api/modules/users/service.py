# api/modules/users/service.py
import secrets
import string

from werkzeug.security import generate_password_hash

from api.shared.exceptions import ForbiddenError, NotFoundError, ValidationError
from . import query

_KODE_CHARS = string.ascii_uppercase + string.digits


def _new_kode():
    return "".join(secrets.choice(_KODE_CHARS) for _ in range(6))


def _guard_superuser_target(id_target, actor_permissions):
    # cegah ADMIN mengambil alih akun SUPER_ADMIN (ganti password / nonaktifkan / ubah role)
    if "*" not in actor_permissions and "*" in query.get_permissions(id_target):
        raise ForbiddenError("Tidak boleh mengubah akun SUPER_ADMIN")


def _clean(data, id_target=None):
    clean = {
        "username": data["username"].strip(),
        "email": (data.get("email") or "").strip() or None,
    }
    conflicts = query.find_conflicts(clean["username"], clean["email"], id_target)
    if conflicts:
        raise ValidationError("Data sudah dipakai user lain", {k: "Sudah dipakai" for k in conflicts})
    password = data.get("password")
    clean["password_hash"] = generate_password_hash(password) if password else None
    return clean


def list_all():
    return query.get_all()


def get(id_user):
    row = query.get_by_id(id_user)
    if not row:
        raise NotFoundError("User tidak ditemukan")
    return row


def _validate_roles(id_roles, actor_permissions):
    id_roles = set(id_roles)
    if not id_roles:
        raise ValidationError("Role wajib diisi", {"id_roles": "Minimal 1 role"})
    roles = query.get_roles_by_ids(id_roles)
    missing = id_roles - {r["id_role"] for r in roles}
    if missing:
        raise ValidationError("Role tidak ditemukan / tidak aktif", {"id_roles": sorted(missing)})
    # hanya SUPER_ADMIN yang boleh memberi role ber-permission "*"
    if "*" not in actor_permissions and any("*" in r["permissions"] for r in roles):
        raise ForbiddenError("Tidak boleh memberi role SUPER_ADMIN")
    return sorted(id_roles)


def create(data, id_actor, actor_permissions):
    id_roles = _validate_roles(data["id_roles"], actor_permissions)
    clean = _clean(data)
    clean["kode_pemulihan"] = _new_kode()
    return get(query.insert(clean, id_roles, id_actor))


def update(id_target, data, id_actor, actor_permissions):
    get(id_target)
    _guard_superuser_target(id_target, actor_permissions)
    query.update(id_target, _clean(data, id_target), id_actor)
    return get(id_target)


def deactivate(id_target, id_actor, actor_permissions):
    if id_target == id_actor:
        raise ValidationError("Tidak boleh menonaktifkan akun sendiri")
    get(id_target)
    _guard_superuser_target(id_target, actor_permissions)
    query.set_active(id_target, 0, id_actor)


def activate(id_target, id_actor, actor_permissions):
    get(id_target)
    _guard_superuser_target(id_target, actor_permissions)
    query.set_active(id_target, 1, id_actor)
    return get(id_target)


def reset_kode_pemulihan(id_target, id_actor, actor_permissions):
    get(id_target)
    _guard_superuser_target(id_target, actor_permissions)
    query.set_kode_pemulihan(id_target, _new_kode(), id_actor)
    return get(id_target)


def set_roles(id_target, id_roles, id_actor, actor_permissions):
    get(id_target)
    _guard_superuser_target(id_target, actor_permissions)
    query.replace_roles(id_target, _validate_roles(id_roles, actor_permissions), id_actor)
    return get(id_target)


# --- dipakai modul pegawai: validasi & siapkan data user, penyimpanan dilakukan modul pegawai ---
def guard_target(id_target, actor_permissions):
    _guard_superuser_target(id_target, actor_permissions)


def prepare_new(data, actor_permissions):
    """Kembalikan (data user bersih, id_roles). Role kosong = PEGAWAI."""
    id_roles = data.get("id_roles") or [query.get_role_id_by_code("PEGAWAI")]
    id_roles = _validate_roles([r for r in id_roles if r is not None], actor_permissions)
    clean = _clean(data)
    clean["kode_pemulihan"] = _new_kode()
    return clean, id_roles


def prepare_update(id_target, data, actor_permissions):
    """Kembalikan (data user bersih, id_roles atau None = role tidak diubah)."""
    _guard_superuser_target(id_target, actor_permissions)
    id_roles = data.get("id_roles")
    if id_roles is not None:
        id_roles = _validate_roles(id_roles, actor_permissions)
    return _clean(data, id_target), id_roles


def set_password(id_target, password, id_actor, actor_permissions):
    get(id_target)
    _guard_superuser_target(id_target, actor_permissions)
    if len(password or "") < 8:
        raise ValidationError("Password minimal 8 karakter", {"password": "Minimal 8 karakter"})
    query.update_password(id_target, generate_password_hash(password), id_actor)
