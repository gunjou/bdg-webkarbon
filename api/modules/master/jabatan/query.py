# api/modules/master/jabatan/query.py
from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita


def get_all():
    sql = text("SELECT * FROM jabatan WHERE is_active = 1 ORDER BY sort_order, name")
    with get_engine().connect() as conn:
        return conn.execute(sql).mappings().all()


def get_by_id(id_jabatan):
    sql = text("SELECT * FROM jabatan WHERE id_jabatan = :id_jabatan")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_jabatan": id_jabatan}).mappings().first()


def find_by_name(name, exclude_id=None):
    """Cari nama sama (case-insensitive), termasuk yang nonaktif — index unik mencakup semua baris."""
    sql = text("""
        SELECT id_jabatan, is_active FROM jabatan
        WHERE lower(name) = lower(:name)
          AND (CAST(:exclude_id AS INTEGER) IS NULL OR id_jabatan <> CAST(:exclude_id AS INTEGER))
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"name": name, "exclude_id": exclude_id}).mappings().first()


def count_active_pegawai(id_jabatan):
    sql = text("SELECT count(*) FROM pegawai WHERE id_jabatan = :id_jabatan AND is_active = 1")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_jabatan": id_jabatan}).scalar()


def insert(data, id_user):
    sql = text("""
        INSERT INTO jabatan (name, sort_order, created_at, created_by)
        VALUES (:name, :sort_order, :now, :id_user)
        RETURNING id_jabatan
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita(), "id_user": id_user}).scalar()


def update(id_jabatan, data, id_user):
    sql = text("""
        UPDATE jabatan SET name = :name, sort_order = :sort_order, updated_at = :now, updated_by = :id_user
        WHERE id_jabatan = :id_jabatan
    """)
    with get_engine().begin() as conn:
        params = {**data, "id_jabatan": id_jabatan, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount


def set_active(id_jabatan, is_active, id_user):
    sql = text("""
        UPDATE jabatan SET is_active = :is_active, updated_at = :now, updated_by = :id_user
        WHERE id_jabatan = :id_jabatan
    """)
    with get_engine().begin() as conn:
        params = {"id_jabatan": id_jabatan, "is_active": is_active, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount
