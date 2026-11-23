# api/modules/jenis_surat/query.py
import json

from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita

LIST_COLUMNS = """id_jenis_surat, code, name, kode_klasifikasi, persyaratan, versi, sort_order,
                  is_active, created_at, created_by, updated_at, updated_by"""


def _json(data):
    return {**data, "skema_form": json.dumps(data["skema_form"]), "persyaratan": json.dumps(data["persyaratan"])}


def get_all(include_inactive=0):
    sql = text(f"""
        SELECT {LIST_COLUMNS} FROM jenis_surat
        WHERE (:include_inactive = 1 OR is_active = 1)
        ORDER BY sort_order, name
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"include_inactive": include_inactive}).mappings().all()


def get_by_id(id_jenis_surat):
    sql = text("SELECT * FROM jenis_surat WHERE id_jenis_surat = :id_jenis_surat")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_jenis_surat": id_jenis_surat}).mappings().first()


def find_by_code(code, exclude_id=None):
    """Termasuk yang nonaktif — UNIQUE (code) mencakup semua baris."""
    sql = text("""
        SELECT id_jenis_surat, is_active FROM jenis_surat
        WHERE code = :code
          AND (CAST(:exclude_id AS INTEGER) IS NULL OR id_jenis_surat <> CAST(:exclude_id AS INTEGER))
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"code": code, "exclude_id": exclude_id}).mappings().first()


def find_by_klasifikasi(klasifikasi, exclude_id=None):
    """Nomor urut per jenis: klasifikasi kembar -> nomor surat kembar. Termasuk yang nonaktif."""
    sql = text("""
        SELECT code FROM jenis_surat
        WHERE kode_klasifikasi = :klasifikasi
          AND (CAST(:exclude_id AS INTEGER) IS NULL OR id_jenis_surat <> CAST(:exclude_id AS INTEGER))
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"klasifikasi": klasifikasi, "exclude_id": exclude_id}).mappings().first()


def count_surat(id_jenis_surat):
    sql = text("SELECT count(*) FROM surat WHERE id_jenis_surat = :id_jenis_surat")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_jenis_surat": id_jenis_surat}).scalar()


def insert(data, id_user):
    sql = text("""
        INSERT INTO jenis_surat (code, name, kode_klasifikasi, skema_form, template_isi, persyaratan, versi,
                                 sort_order, created_at, created_by)
        VALUES (:code, :name, :kode_klasifikasi, CAST(:skema_form AS JSONB), :template_isi,
                CAST(:persyaratan AS JSONB), 1, :sort_order, :now, :id_user)
        RETURNING id_jenis_surat
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**_json(data), "now": get_wita(), "id_user": id_user}).scalar()


def update(id_jenis_surat, data, naik_versi, id_user):
    sql = text("""
        UPDATE jenis_surat SET code = :code, name = :name, kode_klasifikasi = :kode_klasifikasi,
               skema_form = CAST(:skema_form AS JSONB), template_isi = :template_isi,
               persyaratan = CAST(:persyaratan AS JSONB), sort_order = :sort_order,
               versi = versi + :naik_versi, updated_at = :now, updated_by = :id_user
        WHERE id_jenis_surat = :id_jenis_surat
    """)
    with get_engine().begin() as conn:
        params = {**_json(data), "naik_versi": naik_versi, "id_jenis_surat": id_jenis_surat,
                  "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount


def set_active(id_jenis_surat, is_active, id_user):
    sql = text("""
        UPDATE jenis_surat SET is_active = :is_active, updated_at = :now, updated_by = :id_user
        WHERE id_jenis_surat = :id_jenis_surat
    """)
    with get_engine().begin() as conn:
        params = {"id_jenis_surat": id_jenis_surat, "is_active": is_active, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount
