# api/modules/landing/query.py
import json

from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita

KONTEN_KEY = "landing.konten"

# tabel daftar sederhana: (tabel, pk, kolom isian). Nama tabel/kolom hanya dari dict ini (bukan input user).
DAFTAR = {
    "perangkat": ("perangkat_desa", "id_perangkat_desa", ("nama", "jabatan", "foto_path", "urutan")),
    "potensi": ("potensi", "id_potensi", ("judul", "deskripsi", "kategori", "foto_path", "urutan")),
}
BERITA_COLS = ("judul", "slug", "ringkasan", "isi", "sampul_path", "status", "tanggal_terbit")


# ---------------------------------------------------------------- konten (tabel settings)
def get_konten():
    sql = text("SELECT value FROM settings WHERE key = :key")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"key": KONTEN_KEY}).scalar()


def save_konten(value, id_user):
    sql = text("""
        INSERT INTO settings (key, value, description, created_at, created_by)
        VALUES (:key, CAST(:value AS JSONB), 'Konten website desa (landing page)', :now, :id_user)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = :now, updated_by = :id_user
    """)
    with get_engine().begin() as conn:
        conn.execute(sql, {"key": KONTEN_KEY, "value": json.dumps(value), "now": get_wita(), "id_user": id_user})


# ---------------------------------------------------------------- perangkat & potensi
def daftar_all(jenis):
    tabel, pk, _ = DAFTAR[jenis]
    sql = text(f"SELECT * FROM {tabel} WHERE is_active = 1 ORDER BY urutan, {pk}")
    with get_engine().connect() as conn:
        return conn.execute(sql).mappings().all()


def daftar_get(jenis, id_):
    tabel, pk, _ = DAFTAR[jenis]
    sql = text(f"SELECT * FROM {tabel} WHERE {pk} = :id AND is_active = 1")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id": id_}).mappings().first()


def daftar_insert(jenis, data, id_user):
    tabel, pk, cols = DAFTAR[jenis]
    sql = text(f"""
        INSERT INTO {tabel} ({", ".join(cols)}, created_at, created_by)
        VALUES ({", ".join(":" + c for c in cols)}, :now, :id_user) RETURNING {pk}
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita(), "id_user": id_user}).scalar()


def daftar_update(jenis, id_, data, id_user):
    tabel, pk, cols = DAFTAR[jenis]
    sql = text(f"""
        UPDATE {tabel} SET {", ".join(f"{c} = :{c}" for c in cols)}, updated_at = :now, updated_by = :id_user
        WHERE {pk} = :id AND is_active = 1
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "id": id_, "now": get_wita(), "id_user": id_user}).rowcount


def daftar_deactivate(jenis, id_, id_user):
    tabel, pk, _ = DAFTAR[jenis]
    sql = text(f"UPDATE {tabel} SET is_active = 0, updated_at = :now, updated_by = :id_user WHERE {pk} = :id")
    with get_engine().begin() as conn:
        return conn.execute(sql, {"id": id_, "now": get_wita(), "id_user": id_user}).rowcount


# ---------------------------------------------------------------- berita
_LIST_COLS = """id_berita, judul, slug, ringkasan, sampul_path, status, tanggal_terbit,
                created_at, created_by, updated_at, updated_by"""
_FILTER = """
    WHERE is_active = 1
      AND (CAST(:status AS VARCHAR) IS NULL OR status = CAST(:status AS VARCHAR))
      AND (CAST(:q AS VARCHAR) IS NULL OR judul ILIKE '%' || CAST(:q AS VARCHAR) || '%')
      AND (CAST(:sampai AS DATE) IS NULL OR tanggal_terbit <= CAST(:sampai AS DATE))
"""


def berita_list(status, q, sampai, limit, offset):
    """sampai = hanya yang tanggal_terbit <= tanggal ini (dipakai publik)."""
    params = {"status": status, "q": q, "sampai": sampai, "limit": limit, "offset": offset}
    with get_engine().connect() as conn:
        total = conn.execute(text(f"SELECT count(*) FROM berita {_FILTER}"), params).scalar()
        rows = conn.execute(text(f"""
            SELECT {_LIST_COLS} FROM berita {_FILTER}
            ORDER BY tanggal_terbit DESC NULLS FIRST, id_berita DESC LIMIT :limit OFFSET :offset
        """), params).mappings().all()
    return rows, total


def berita_get(id_berita):
    sql = text("SELECT * FROM berita WHERE id_berita = :id AND is_active = 1")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id": id_berita}).mappings().first()


def berita_get_publik(slug, sampai):
    sql = text("""
        SELECT * FROM berita
        WHERE slug = :slug AND is_active = 1 AND status = 'terbit' AND tanggal_terbit <= :sampai
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"slug": slug, "sampai": sampai}).mappings().first()


def slug_dipakai(slug, exclude_id=None):
    # termasuk berita nonaktif: constraint uq_berita_slug berlaku untuk semua baris
    sql = text("""
        SELECT 1 FROM berita
        WHERE slug = :slug AND (CAST(:exclude_id AS INTEGER) IS NULL OR id_berita <> CAST(:exclude_id AS INTEGER))
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"slug": slug, "exclude_id": exclude_id}).first() is not None


def berita_insert(data, id_user):
    sql = text(f"""
        INSERT INTO berita ({", ".join(BERITA_COLS)}, created_at, created_by)
        VALUES ({", ".join(":" + c for c in BERITA_COLS)}, :now, :id_user) RETURNING id_berita
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita(), "id_user": id_user}).scalar()


def berita_update(id_berita, data, id_user):
    sql = text(f"""
        UPDATE berita SET {", ".join(f"{c} = :{c}" for c in BERITA_COLS)}, updated_at = :now, updated_by = :id_user
        WHERE id_berita = :id AND is_active = 1
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "id": id_berita, "now": get_wita(), "id_user": id_user}).rowcount


def berita_deactivate(id_berita, id_user):
    sql = text("UPDATE berita SET is_active = 0, updated_at = :now, updated_by = :id_user WHERE id_berita = :id")
    with get_engine().begin() as conn:
        return conn.execute(sql, {"id": id_berita, "now": get_wita(), "id_user": id_user}).rowcount
