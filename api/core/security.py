# api/core/security.py
from functools import wraps

from flask_jwt_extended import verify_jwt_in_request, get_jwt

from api.shared.exceptions import ForbiddenError


def _require(claim, expected):
    # permission "*" = lolos semua cek role & permission (dipakai SUPER_ADMIN)
    wanted = {expected} if isinstance(expected, str) else set(expected)

    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            is_superuser = "*" in claims.get("permissions", [])
            if not is_superuser and not wanted & set(claims.get(claim, [])):
                raise ForbiddenError("Akses tidak diizinkan")
            return fn(*args, **kwargs)
        return decorator
    return wrapper


def role_required(expected_roles):
    """Lolos jika user punya salah satu role. Contoh: @role_required(["ADMIN", "SEKDES"])"""
    return _require("roles", expected_roles)


def permission_required(expected_permissions):
    """Lolos jika user punya salah satu permission. Contoh: @permission_required("perizinan.review")"""
    return _require("permissions", expected_permissions)
