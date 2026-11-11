# api/modules/pegawai/query.py
# Pegawai & akun user-nya ditulis dalam SATU transaksi agar tidak ada pegawai tanpa user (atau sebaliknya).
# Validasi data user dilakukan users.service (prepare_new / prepare_update).
from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita

# embedding tidak di-SELECT (besar); cukup flag has_face
_SELECT = """
    SELECT p.id_pegawai, p.full_name, p.nip, p.phone, p.photo_path,
           (p.embedding IS NOT NULL) AS has_face,
           p.id_jabatan, j.name AS jabatan_name,
           p.id_jadwal_kerja, jk.name AS jadwal_kerja_name,
           p.is_active, p.created_at, p.updated_at,
           u.id_user, u.username, u.email, u.is_active AS user_is_active, u.last_login_at,
           COALESCE((
               SELECT json_agg(json_build_object('id_role', r.id_role, 'code', r.code, 'name', r.name)
                               ORDER BY r.code)
               FROM user_roles ur JOIN roles r ON r.id_role = ur.id_role
               WHERE ur.id_user = u.id_user
           ), '[]') AS roles
    FROM pegawai p
    JOIN jabatan j ON j.id_jabatan = p.id_jabatan
    LEFT JOIN jadwal_kerja jk ON jk.id_jadwal_kerja = p.id_jadwal_kerja
    LEFT JOIN users u ON u.id_pegawai = p.id_pegawai
"""

_INSERT_ROLES = text("""
    INSERT INTO user_roles (id_user, id_role, created_at, created_by)
    VALUES (:id_target, :id_role, :now, :actor)
""")


def get_all():
    sql = text(_SELECT + " WHERE p.is_active = 1 ORDER BY j.sort_order, p.full_name")
    with get_engine().connect() as conn:
        return conn.execute(sql).mappings().all()


def get_by_id(id_pegawai):
    sql = text(_SELECT + " WHERE p.id_pegawai = :id_pegawai")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_pegawai": id_pegawai}).mappings().first()


def find_by_nip(nip, exclude_id=None):
    """Index unik nip mencakup pegawai nonaktif."""
    sql = text("""
        SELECT id_pegawai, full_name FROM pegawai
        WHERE nip = :nip
          AND (CAST(:exclude_id AS INTEGER) IS NULL OR id_pegawai <> CAST(:exclude_id AS INTEGER))
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"nip": nip, "exclude_id": exclude_id}).mappings().first()


def insert(pegawai, user, id_roles, actor):
    now = get_wita()
    base = {"now": now, "actor": actor}
    with get_engine().begin() as conn:
        id_pegawai = conn.execute(text("""
            INSERT INTO pegawai (id_jabatan, id_jadwal_kerja, nip, full_name, phone, photo_path, embedding,
                                 created_at, created_by)
            VALUES (:id_jabatan, :id_jadwal_kerja, :nip, :full_name, :phone, :photo_path,
                    CAST(:embedding AS REAL[]), :now, :actor)
            RETURNING id_pegawai
        """), {**pegawai, **base}).scalar()
        id_user = conn.execute(text("""
            INSERT INTO users (id_pegawai, username, email, password_hash, kode_pemulihan, created_at, created_by)
            VALUES (:id_pegawai, :username, :email, :password_hash, :kode_pemulihan, :now, :actor)
            RETURNING id_user
        """), {**user, **base, "id_pegawai": id_pegawai}).scalar()
        conn.execute(_INSERT_ROLES, [{**base, "id_target": id_user, "id_role": r} for r in id_roles])
        return id_pegawai


def update(id_pegawai, pegawai, id_user, user, id_roles, actor):
    """id_roles None = role tidak diubah. Password tidak disentuh (endpoint sendiri)."""
    base = {"now": get_wita(), "actor": actor}
    with get_engine().begin() as conn:
        conn.execute(text("""
            UPDATE pegawai SET id_jabatan = :id_jabatan, id_jadwal_kerja = :id_jadwal_kerja, nip = :nip,
                   full_name = :full_name, phone = :phone, updated_at = :now, updated_by = :actor
            WHERE id_pegawai = :id_pegawai
        """), {**pegawai, **base, "id_pegawai": id_pegawai})
        conn.execute(text("""
            UPDATE users SET username = :username, email = :email, updated_at = :now, updated_by = :actor
            WHERE id_user = :id_user
        """), {**user, **base, "id_user": id_user})
        if id_roles is not None:
            conn.execute(text("DELETE FROM user_roles WHERE id_user = :id_user"), {"id_user": id_user})
            conn.execute(_INSERT_ROLES, [{**base, "id_target": id_user, "id_role": r} for r in id_roles])


def set_active(id_pegawai, is_active, actor):
    """Pegawai & akun user-nya diaktifkan/nonaktifkan bersamaan."""
    params = {"id_pegawai": id_pegawai, "is_active": is_active, "now": get_wita(), "actor": actor}
    with get_engine().begin() as conn:
        for table in ("pegawai", "users"):
            conn.execute(text(f"""
                UPDATE {table} SET is_active = :is_active, updated_at = :now, updated_by = :actor
                WHERE id_pegawai = :id_pegawai
            """), params)


def set_photo(id_pegawai, photo_path, embedding, actor):
    sql = text("""
        UPDATE pegawai SET photo_path = :photo_path, embedding = CAST(:embedding AS REAL[]),
               updated_at = :now, updated_by = :actor
        WHERE id_pegawai = :id_pegawai
    """)
    with get_engine().begin() as conn:
        params = {"id_pegawai": id_pegawai, "photo_path": photo_path, "embedding": embedding,
                  "now": get_wita(), "actor": actor}
        return conn.execute(sql, params).rowcount
