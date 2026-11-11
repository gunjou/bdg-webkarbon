# api/modules/users/query.py
from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita

# password_hash tidak pernah di-SELECT
_SELECT = """
    SELECT u.id_user, u.username, u.email,
           u.last_login_at, u.is_active, u.created_at, u.updated_at,
           COALESCE((
               SELECT json_agg(json_build_object('id_role', r.id_role, 'code', r.code, 'name', r.name)
                               ORDER BY r.code)
               FROM user_roles ur JOIN roles r ON r.id_role = ur.id_role
               WHERE ur.id_user = u.id_user
           ), '[]') AS roles
    FROM users u
"""


def get_all():
    sql = text(_SELECT + " WHERE u.is_active = 1 ORDER BY u.id_user")
    with get_engine().connect() as conn:
        return conn.execute(sql).mappings().all()


def get_by_id(id_user):
    sql = text(_SELECT.replace("SELECT u.id_user", "SELECT u.kode_pemulihan, u.id_user", 1)
               + " WHERE u.id_user = :id_user")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_user": id_user}).mappings().first()


def find_conflicts(username, email, exclude_id=None):
    """Kembalikan daftar field yang sudah dipakai user lain."""
    sql = text("""
        SELECT
            bool_or(lower(username) = lower(CAST(:username AS TEXT))) AS username,
            bool_or(CAST(:email AS TEXT) IS NOT NULL AND lower(email) = lower(CAST(:email AS TEXT))) AS email
        FROM users
        WHERE (CAST(:exclude_id AS INTEGER) IS NULL OR id_user <> CAST(:exclude_id AS INTEGER))
    """)
    params = {"username": username, "email": email, "exclude_id": exclude_id}
    with get_engine().connect() as conn:
        row = conn.execute(sql, params).mappings().first()
    return [k for k, v in row.items() if v]


def get_permissions(id_user):
    sql = text("""
        SELECT r.permissions FROM user_roles ur JOIN roles r ON r.id_role = ur.id_role
        WHERE ur.id_user = :id_user
    """)
    with get_engine().connect() as conn:
        return {p for row in conn.execute(sql, {"id_user": id_user}).scalars() for p in row}


def get_roles_by_ids(id_roles):
    sql = text("SELECT id_role, code, permissions FROM roles WHERE id_role = ANY(:ids) AND is_active = 1")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"ids": list(id_roles)}).mappings().all()


_INSERT_ROLES = text("""
    INSERT INTO user_roles (id_user, id_role, created_at, created_by)
    VALUES (:id_target, :id_role, :now, :id_user)
""")


def insert(data, id_roles, id_user):
    """Insert user + role-nya dalam satu transaksi."""
    sql = text("""
        INSERT INTO users (username, email, password_hash, kode_pemulihan, created_at, created_by)
        VALUES (:username, :email, :password_hash, :kode_pemulihan, :now, :id_user)
        RETURNING id_user
    """)
    now = get_wita()
    with get_engine().begin() as conn:
        id_target = conn.execute(sql, {**data, "now": now, "id_user": id_user}).scalar()
        conn.execute(_INSERT_ROLES, [{"id_target": id_target, "id_role": r, "now": now, "id_user": id_user}
                                     for r in id_roles])
        return id_target


def update(id_target, data, id_user):
    # password_hash NULL = tidak diganti
    sql = text("""
        UPDATE users SET username = :username, email = :email,
               password_hash = COALESCE(:password_hash, password_hash),
               updated_at = :now, updated_by = :id_user
        WHERE id_user = :id_target
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "id_target": id_target, "now": get_wita(), "id_user": id_user}).rowcount


def set_active(id_target, is_active, id_user):
    sql = text("""
        UPDATE users SET is_active = :is_active, updated_at = :now, updated_by = :id_user
        WHERE id_user = :id_target
    """)
    with get_engine().begin() as conn:
        params = {"id_target": id_target, "is_active": is_active, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount


def set_kode_pemulihan(id_target, kode, id_user):
    sql = text("""
        UPDATE users SET kode_pemulihan = :kode, updated_at = :now, updated_by = :id_user
        WHERE id_user = :id_target
    """)
    with get_engine().begin() as conn:
        params = {"id_target": id_target, "kode": kode, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount


def replace_roles(id_target, id_roles, id_user):
    """Ganti seluruh role user dalam satu transaksi."""
    now = get_wita()
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM user_roles WHERE id_user = :id_target"), {"id_target": id_target})
        conn.execute(_INSERT_ROLES, [{"id_target": id_target, "id_role": r, "now": now, "id_user": id_user}
                                     for r in id_roles])


def get_role_id_by_code(code):
    sql = text("SELECT id_role FROM roles WHERE code = :code AND is_active = 1")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"code": code}).scalar()


def update_password(id_target, password_hash, id_user):
    sql = text("""
        UPDATE users SET password_hash = :password_hash, updated_at = :now, updated_by = :id_user
        WHERE id_user = :id_target
    """)
    with get_engine().begin() as conn:
        params = {"id_target": id_target, "password_hash": password_hash, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount
