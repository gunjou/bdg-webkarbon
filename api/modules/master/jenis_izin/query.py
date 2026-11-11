# api/modules/master/jenis_izin/query.py
from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita


def get_all():
    sql = text("SELECT * FROM jenis_izin WHERE is_active = 1 ORDER BY id_jenis_izin, name")
    with get_engine().connect() as conn:
        return conn.execute(sql).mappings().all()


def get_by_id(id_jenis_izin):
    sql = text("SELECT * FROM jenis_izin WHERE id_jenis_izin = :id_jenis_izin")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_jenis_izin": id_jenis_izin}).mappings().first()


def find_by_code(code, exclude_id=None):
    """Termasuk yang nonaktif — constraint UNIQUE (code) mencakup semua baris."""
    sql = text("""
        SELECT id_jenis_izin, is_active FROM jenis_izin
        WHERE upper(code) = upper(:code)
          AND (CAST(:exclude_id AS INTEGER) IS NULL OR id_jenis_izin <> CAST(:exclude_id AS INTEGER))
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"code": code, "exclude_id": exclude_id}).mappings().first()


def count_pending_perizinan(id_jenis_izin):
    sql = text("SELECT count(*) FROM perizinan WHERE id_jenis_izin = :id_jenis_izin AND status = 'diajukan'")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_jenis_izin": id_jenis_izin}).scalar()


def insert(data, id_user):
    sql = text("""
        INSERT INTO jenis_izin (code, name, butuh_lampiran, dihitung_hadir, created_at, created_by)
        VALUES (:code, :name, :butuh_lampiran, :dihitung_hadir, :now, :id_user)
        RETURNING id_jenis_izin
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita(), "id_user": id_user}).scalar()


def update(id_jenis_izin, data, id_user):
    sql = text("""
        UPDATE jenis_izin SET code = :code, name = :name, butuh_lampiran = :butuh_lampiran,
               dihitung_hadir = :dihitung_hadir, updated_at = :now, updated_by = :id_user
        WHERE id_jenis_izin = :id_jenis_izin
    """)
    with get_engine().begin() as conn:
        params = {**data, "id_jenis_izin": id_jenis_izin, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount


def set_active(id_jenis_izin, is_active, id_user):
    sql = text("""
        UPDATE jenis_izin SET is_active = :is_active, updated_at = :now, updated_by = :id_user
        WHERE id_jenis_izin = :id_jenis_izin
    """)
    with get_engine().begin() as conn:
        params = {"id_jenis_izin": id_jenis_izin, "is_active": is_active, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount
