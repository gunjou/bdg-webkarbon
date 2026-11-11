# api/modules/auth/query.py
from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita


def get_user_by_username(username):
    sql = text("""
        SELECT u.id_user, u.id_pegawai, u.username, u.email, u.password_hash, u.kode_pemulihan,
               u.is_active, p.is_active AS pegawai_is_active, p.full_name, p.photo_path
        FROM users u
        LEFT JOIN pegawai p ON p.id_pegawai = u.id_pegawai
        WHERE lower(u.username) = lower(:username)
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"username": username}).mappings().first()


def get_user_by_id(id_user):
    sql = text("""
        SELECT u.id_user, u.id_pegawai, u.username, u.email,
               u.is_active, p.is_active AS pegawai_is_active, p.full_name, p.photo_path
        FROM users u
        LEFT JOIN pegawai p ON p.id_pegawai = u.id_pegawai
        WHERE u.id_user = :id_user
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_user": id_user}).mappings().first()


def get_active_roles(id_user):
    sql = text("""
        SELECT r.code, r.permissions
        FROM user_roles ur
        JOIN roles r ON r.id_role = ur.id_role
        WHERE ur.id_user = :id_user AND r.is_active = 1
        ORDER BY r.code
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_user": id_user}).mappings().all()


def update_last_login(id_user):
    sql = text("UPDATE users SET last_login_at = :now WHERE id_user = :id_user")
    with get_engine().begin() as conn:
        conn.execute(sql, {"id_user": id_user, "now": get_wita()})


def insert_login_failure(id_user, error_code, error_message=None):
    sql = text("""
        INSERT INTO login_failures (id_user, error_code, error_message, created_at)
        VALUES (:id_user, :error_code, :error_message, :now)
    """)
    with get_engine().begin() as conn:
        conn.execute(sql, {"id_user": id_user, "error_code": error_code, "error_message": error_message, "now": get_wita()})
