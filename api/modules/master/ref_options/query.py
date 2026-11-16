# api/modules/master/ref_options/query.py
from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita


def get_all(group_code=None, include_inactive=0):
    sql = text("""
        SELECT * FROM ref_options
        WHERE (CAST(:group_code AS VARCHAR) IS NULL OR group_code = :group_code)
          AND (:include_inactive = 1 OR is_active = 1)
        ORDER BY group_code, sort_order, label
    """)
    with get_engine().connect() as conn:
        params = {"group_code": group_code, "include_inactive": include_inactive}
        return conn.execute(sql, params).mappings().all()


def get_by_id(id_ref_option):
    sql = text("SELECT * FROM ref_options WHERE id_ref_option = :id_ref_option")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_ref_option": id_ref_option}).mappings().first()


def find_by_code(group_code, code, exclude_id=None):
    """Termasuk yang nonaktif — UNIQUE (group_code, code) mencakup semua baris."""
    sql = text("""
        SELECT id_ref_option, is_active FROM ref_options
        WHERE group_code = :group_code AND code = :code
          AND (CAST(:exclude_id AS INTEGER) IS NULL OR id_ref_option <> CAST(:exclude_id AS INTEGER))
    """)
    with get_engine().connect() as conn:
        params = {"group_code": group_code, "code": code, "exclude_id": exclude_id}
        return conn.execute(sql, params).mappings().first()


def get_active_codes(group_codes):
    """{group_code: set(code)} untuk validasi isian tabel lain."""
    sql = text("SELECT group_code, code FROM ref_options WHERE is_active = 1 AND group_code = ANY(:groups)")
    with get_engine().connect() as conn:
        rows = conn.execute(sql, {"groups": list(group_codes)}).mappings().all()
    out = {g: set() for g in group_codes}
    for r in rows:
        out[r["group_code"]].add(r["code"])
    return out


def insert(data, id_user):
    sql = text("""
        INSERT INTO ref_options (group_code, code, label, sort_order, created_at, created_by)
        VALUES (:group_code, :code, :label, :sort_order, :now, :id_user)
        RETURNING id_ref_option
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita(), "id_user": id_user}).scalar()


def update(id_ref_option, data, id_user):
    sql = text("""
        UPDATE ref_options SET group_code = :group_code, code = :code, label = :label, sort_order = :sort_order,
               updated_at = :now, updated_by = :id_user
        WHERE id_ref_option = :id_ref_option
    """)
    with get_engine().begin() as conn:
        params = {**data, "id_ref_option": id_ref_option, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount


def set_active(id_ref_option, is_active, id_user):
    sql = text("""
        UPDATE ref_options SET is_active = :is_active, updated_at = :now, updated_by = :id_user
        WHERE id_ref_option = :id_ref_option
    """)
    with get_engine().begin() as conn:
        params = {"id_ref_option": id_ref_option, "is_active": is_active, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount
