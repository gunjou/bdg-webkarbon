# api/modules/penduduk/query.py
from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita

COLUMNS = ("nik", "no_kk", "full_name", "tempat_lahir", "tanggal_lahir", "jenis_kelamin", "agama", "pekerjaan",
           "status_perkawinan", "kewarganegaraan", "dusun", "rt", "rw", "alamat")


def search(f):
    """f: nomor (awalan NIK/KK) | nama (awalan, lower) | dusun | include_inactive | limit | offset."""
    sql = text("""
        SELECT * FROM penduduk
        WHERE (:include_inactive = 1 OR is_active = 1)
          AND (CAST(:dusun AS VARCHAR) IS NULL OR dusun = :dusun)
          AND (CAST(:nomor AS VARCHAR) IS NULL OR nik LIKE :nomor || '%' OR no_kk LIKE :nomor || '%')
          AND (CAST(:nama AS VARCHAR) IS NULL OR lower(full_name) LIKE :nama || '%')
        ORDER BY full_name, id_penduduk
        LIMIT :limit OFFSET :offset
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, f).mappings().all()


def get_by_id(id_penduduk):
    sql = text("SELECT * FROM penduduk WHERE id_penduduk = :id_penduduk")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_penduduk": id_penduduk}).mappings().first()


def find_by_nik(nik, exclude_id=None):
    """Termasuk yang nonaktif — index unik NIK mencakup semua baris."""
    sql = text("""
        SELECT id_penduduk, full_name, is_active FROM penduduk
        WHERE nik = :nik
          AND (CAST(:exclude_id AS INTEGER) IS NULL OR id_penduduk <> CAST(:exclude_id AS INTEGER))
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"nik": nik, "exclude_id": exclude_id}).mappings().first()


def insert(data, id_user):
    sql = text(f"""
        INSERT INTO penduduk ({", ".join(COLUMNS)}, created_at, created_by)
        VALUES ({", ".join(":" + c for c in COLUMNS)}, :now, :id_user)
        RETURNING id_penduduk
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita(), "id_user": id_user}).scalar()


def update(id_penduduk, data, id_user):
    sql = text(f"""
        UPDATE penduduk SET {", ".join(f"{c} = :{c}" for c in COLUMNS)}, updated_at = :now, updated_by = :id_user
        WHERE id_penduduk = :id_penduduk
    """)
    with get_engine().begin() as conn:
        params = {**data, "id_penduduk": id_penduduk, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount


def set_active(id_penduduk, is_active, id_user):
    sql = text("""
        UPDATE penduduk SET is_active = :is_active, updated_at = :now, updated_by = :id_user
        WHERE id_penduduk = :id_penduduk
    """)
    with get_engine().begin() as conn:
        params = {"id_penduduk": id_penduduk, "is_active": is_active, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount
