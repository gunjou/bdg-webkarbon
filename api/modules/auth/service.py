# api/modules/auth/service.py
import hmac

from flask_jwt_extended import create_access_token, create_refresh_token
from werkzeug.security import check_password_hash, generate_password_hash

from api.shared.exceptions import AuthError, ForbiddenError, ValidationError
from . import query

# hash dummy agar waktu respons username-tidak-ada ≈ password-salah (cegah enumerasi username)
_DUMMY_HASH = generate_password_hash("dummy-password")


def _load_roles(id_user):
    rows = query.get_active_roles(id_user)
    roles = [r["code"] for r in rows]
    permissions = sorted({p for r in rows for p in r["permissions"]})
    return roles, permissions


def _check_account(user, roles):
    """Kembalikan (error_code, pesan) jika akun tidak boleh login, atau None."""
    if user["is_active"] != 1:
        return "USER_INACTIVE", "Akun tidak aktif"
    if user["id_pegawai"] is not None and user["pegawai_is_active"] != 1:
        return "PEGAWAI_INACTIVE", "Pegawai tidak aktif"
    if not roles:
        return "NO_ACTIVE_ROLE", "Akun belum memiliki role aktif"
    return None


def _user_payload(user, roles, permissions):
    return {
        "id_user": user["id_user"],
        "id_pegawai": user["id_pegawai"],
        "username": user["username"],
        "email": user["email"],
        "full_name": user["full_name"],
        "photo_path": user["photo_path"],
        "roles": roles,
        "permissions": permissions,
    }


def _claims(user, roles, permissions):
    return {"id_pegawai": user["id_pegawai"], "roles": roles, "permissions": permissions}


def _verify_credential(user, secret):
    """Cek password dulu, jika salah cek kode pemulihan. None = cocok, selain itu error_code."""
    if check_password_hash(user["password_hash"], secret):
        return None
    stored = user["kode_pemulihan"]
    # compare_digest: waktu perbandingan konstan, cegah tebak kode per karakter
    if stored and hmac.compare_digest(stored.encode(), secret.strip().encode()):
        return None
    return "WRONG_PASSWORD"  # password & kode pemulihan sama-sama salah


def login(username, password):
    if not password:
        raise ValidationError("Password wajib diisi", errors={"password": "required"})

    user = query.get_user_by_username(username)
    if not user:
        check_password_hash(_DUMMY_HASH, password)  # samakan waktu respons dgn password salah
        raise AuthError("Username atau kredensial salah")

    failure = _verify_credential(user, password)
    if failure:
        message = "Username atau kredensial salah"
        query.insert_login_failure(user["id_user"], failure, message)
        raise AuthError(message)

    roles, permissions = _load_roles(user["id_user"])
    problem = _check_account(user, roles)
    if problem:
        code, message = problem
        query.insert_login_failure(user["id_user"], code, message)
        raise ForbiddenError(message)

    query.update_last_login(user["id_user"])
    identity = str(user["id_user"])
    claims = _claims(user, roles, permissions)
    return {
        "access_token": create_access_token(identity=identity, additional_claims=claims),
        "refresh_token": create_refresh_token(identity=identity),
        "user": _user_payload(user, roles, permissions),
    }


def refresh(id_user):
    """Buat access token baru. Status akun & role dibaca ulang dari DB, jadi perubahan role langsung berlaku."""
    user = query.get_user_by_id(int(id_user))
    if not user:
        raise AuthError("Akun tidak ditemukan")
    roles, permissions = _load_roles(user["id_user"])
    problem = _check_account(user, roles)
    if problem:
        raise ForbiddenError(problem[1])
    return {
        "access_token": create_access_token(
            identity=str(user["id_user"]),
            additional_claims=_claims(user, roles, permissions)),
    }


def me(id_user):
    user = query.get_user_by_id(int(id_user))
    if not user:
        raise AuthError("Akun tidak ditemukan")
    roles, permissions = _load_roles(user["id_user"])
    return _user_payload(user, roles, permissions)
