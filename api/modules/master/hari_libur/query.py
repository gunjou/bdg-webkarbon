# api/modules/master/hari_libur/query.py
from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita


def get_all(tahun=None):
    sql = text("""
        SELECT * FROM hari_libur
        WHERE is_active = 1
          AND (CAST(:tahun AS INTEGER) IS NULL OR EXTRACT(YEAR FROM tanggal) = CAST(:tahun AS INTEGER))
        ORDER BY tanggal
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"tahun": tahun}).mappings().all()


def get_by_id(id_hari_libur):
    sql = text("SELECT * FROM hari_libur WHERE id_hari_libur = :id_hari_libur")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_hari_libur": id_hari_libur}).mappings().first()


def find_active_by_tanggal(tanggal, exclude_id=None):
    """Index unik parsial: 1 hari libur aktif per tanggal."""
    sql = text("""
        SELECT id_hari_libur, name FROM hari_libur
        WHERE is_active = 1 AND tanggal = :tanggal
          AND (CAST(:exclude_id AS INTEGER) IS NULL OR id_hari_libur <> CAST(:exclude_id AS INTEGER))
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"tanggal": tanggal, "exclude_id": exclude_id}).mappings().first()


def insert(data, id_user):
    sql = text("""
        INSERT INTO hari_libur (tanggal, name, jenis, created_at, created_by)
        VALUES (:tanggal, :name, :jenis, :now, :id_user)
        RETURNING id_hari_libur
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita(), "id_user": id_user}).scalar()


def update(id_hari_libur, data, id_user):
    sql = text("""
        UPDATE hari_libur SET tanggal = :tanggal, name = :name, jenis = :jenis,
               updated_at = :now, updated_by = :id_user
        WHERE id_hari_libur = :id_hari_libur
    """)
    with get_engine().begin() as conn:
        params = {**data, "id_hari_libur": id_hari_libur, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount


def set_active(id_hari_libur, is_active, id_user):
    sql = text("""
        UPDATE hari_libur SET is_active = :is_active, updated_at = :now, updated_by = :id_user
        WHERE id_hari_libur = :id_hari_libur
    """)
    with get_engine().begin() as conn:
        params = {"id_hari_libur": id_hari_libur, "is_active": is_active, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount
