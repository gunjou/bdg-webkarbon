# api/modules/master/jadwal_kerja/query.py
from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita


def get_all():
    sql = text("SELECT * FROM jadwal_kerja WHERE is_active = 1 ORDER BY name")
    with get_engine().connect() as conn:
        return conn.execute(sql).mappings().all()


def get_by_id(id_jadwal_kerja):
    sql = text("SELECT * FROM jadwal_kerja WHERE id_jadwal_kerja = :id_jadwal_kerja")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_jadwal_kerja": id_jadwal_kerja}).mappings().first()


def find_active_by_name(name, exclude_id=None):
    sql = text("""
        SELECT id_jadwal_kerja FROM jadwal_kerja
        WHERE is_active = 1 AND lower(name) = lower(:name)
          AND (CAST(:exclude_id AS INTEGER) IS NULL OR id_jadwal_kerja <> CAST(:exclude_id AS INTEGER))
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"name": name, "exclude_id": exclude_id}).first()


def count_active_pegawai(id_jadwal_kerja):
    sql = text("SELECT count(*) FROM pegawai WHERE id_jadwal_kerja = :id_jadwal_kerja AND is_active = 1")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_jadwal_kerja": id_jadwal_kerja}).scalar()


def insert(data, id_user):
    sql = text("""
        INSERT INTO jadwal_kerja (name, jadwal_harian, toleransi_terlambat_menit, created_at, created_by)
        VALUES (:name, CAST(:jadwal_harian AS JSONB), :toleransi_terlambat_menit, :now, :id_user)
        RETURNING id_jadwal_kerja
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita(), "id_user": id_user}).scalar()


def update(id_jadwal_kerja, data, id_user):
    sql = text("""
        UPDATE jadwal_kerja SET name = :name, jadwal_harian = CAST(:jadwal_harian AS JSONB),
               toleransi_terlambat_menit = :toleransi_terlambat_menit, updated_at = :now, updated_by = :id_user
        WHERE id_jadwal_kerja = :id_jadwal_kerja
    """)
    with get_engine().begin() as conn:
        params = {**data, "id_jadwal_kerja": id_jadwal_kerja, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount


def set_active(id_jadwal_kerja, is_active, id_user):
    sql = text("""
        UPDATE jadwal_kerja SET is_active = :is_active, updated_at = :now, updated_by = :id_user
        WHERE id_jadwal_kerja = :id_jadwal_kerja
    """)
    with get_engine().begin() as conn:
        params = {"id_jadwal_kerja": id_jadwal_kerja, "is_active": is_active,
                  "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount
