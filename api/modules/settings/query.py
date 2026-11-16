# api/modules/settings/query.py
import json

from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita


def get_values(keys):
    sql = text("SELECT key, value FROM settings WHERE key = ANY(:keys)")
    with get_engine().connect() as conn:
        return {r["key"]: r["value"] for r in conn.execute(sql, {"keys": list(keys)}).mappings()}


def upsert(values, descriptions, id_user):
    """values = {key: value}. Satu transaksi."""
    sql = text("""
        INSERT INTO settings (key, value, description, created_at, created_by)
        VALUES (:key, CAST(:value AS JSONB), :description, :now, :id_user)
        ON CONFLICT (key) DO UPDATE
           SET value = EXCLUDED.value, updated_at = :now, updated_by = :id_user
    """)
    now = get_wita()
    with get_engine().begin() as conn:
        for key, value in values.items():
            conn.execute(sql, {"key": key, "value": json.dumps(value), "description": descriptions[key],
                               "now": now, "id_user": id_user})
