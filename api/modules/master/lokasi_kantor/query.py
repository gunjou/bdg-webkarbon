# api/modules/master/lokasi_kantor/query.py
from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita


def get_all():
    sql = text("SELECT * FROM lokasi_kantor WHERE is_active = 1 ORDER BY name")
    with get_engine().connect() as conn:
        return conn.execute(sql).mappings().all()


def get_by_id(id_lokasi_kantor):
    sql = text("SELECT * FROM lokasi_kantor WHERE id_lokasi_kantor = :id_lokasi_kantor")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_lokasi_kantor": id_lokasi_kantor}).mappings().first()


def find_active_by_name(name, exclude_id=None):
    sql = text("""
        SELECT id_lokasi_kantor FROM lokasi_kantor
        WHERE is_active = 1 AND lower(name) = lower(:name)
          AND (CAST(:exclude_id AS INTEGER) IS NULL OR id_lokasi_kantor <> CAST(:exclude_id AS INTEGER))
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"name": name, "exclude_id": exclude_id}).first()


def count_active_pegawai(id_lokasi_kantor):
    sql = text("SELECT count(*) FROM pegawai WHERE id_lokasi_kantor = :id_lokasi_kantor AND is_active = 1")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_lokasi_kantor": id_lokasi_kantor}).scalar()


def insert(data, id_user):
    sql = text("""
        INSERT INTO lokasi_kantor (name, latitude, longitude, radius_meter, created_at, created_by)
        VALUES (:name, :latitude, :longitude, :radius_meter, :now, :id_user)
        RETURNING id_lokasi_kantor
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita(), "id_user": id_user}).scalar()


def update(id_lokasi_kantor, data, id_user):
    sql = text("""
        UPDATE lokasi_kantor SET name = :name, latitude = :latitude, longitude = :longitude,
               radius_meter = :radius_meter, updated_at = :now, updated_by = :id_user
        WHERE id_lokasi_kantor = :id_lokasi_kantor
    """)
    with get_engine().begin() as conn:
        params = {**data, "id_lokasi_kantor": id_lokasi_kantor, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount


def set_active(id_lokasi_kantor, is_active, id_user):
    sql = text("""
        UPDATE lokasi_kantor SET is_active = :is_active, updated_at = :now, updated_by = :id_user
        WHERE id_lokasi_kantor = :id_lokasi_kantor
    """)
    with get_engine().begin() as conn:
        params = {"id_lokasi_kantor": id_lokasi_kantor, "is_active": is_active,
                  "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount
