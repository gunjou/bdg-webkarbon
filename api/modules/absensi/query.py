# api/modules/absensi/query.py
# absensi & absensi_gagal append-only: hanya INSERT & SELECT.
import json

from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita

_ABSENSI_COLS = """
    a.id_absensi, a.id_pegawai, p.full_name, a.id_lokasi_kantor, lk.name AS lokasi_kantor_name,
    a.tanggal, a.jenis, a.waktu_absen, a.latitude, a.longitude, a.akurasi_gps, a.jarak_meter,
    a.skor_wajah, a.jam_jadwal, a.terlambat_menit, a.status, a.created_at
"""


def get_settings(keys):
    sql = text("SELECT key, value FROM settings WHERE key = ANY(:keys)")
    with get_engine().connect() as conn:
        return {r["key"]: r["value"] for r in conn.execute(sql, {"keys": list(keys)}).mappings()}


def get_context(id_user, tanggal):
    """Pegawai milik user + jadwal + info hari libur pada tanggal tsb."""
    sql = text("""
        SELECT p.id_pegawai, p.full_name, p.is_active, p.embedding, p.id_lokasi_kantor, p.id_jadwal_kerja,
               jk.name AS jadwal_kerja_name, jk.jadwal_harian, jk.toleransi_terlambat_menit,
               (SELECT name FROM hari_libur WHERE tanggal = :tanggal AND is_active = 1) AS libur
        FROM users u
        JOIN pegawai p ON p.id_pegawai = u.id_pegawai
        LEFT JOIN jadwal_kerja jk ON jk.id_jadwal_kerja = p.id_jadwal_kerja
        WHERE u.id_user = :id_user
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_user": id_user, "tanggal": tanggal}).mappings().first()


def get_lokasi_aktif(id_lokasi_kantor=None):
    """id_lokasi_kantor None = semua lokasi aktif."""
    sql = text("""
        SELECT id_lokasi_kantor, name, latitude, longitude, radius_meter FROM lokasi_kantor
        WHERE is_active = 1
          AND (CAST(:id AS INTEGER) IS NULL OR id_lokasi_kantor = CAST(:id AS INTEGER))
        ORDER BY name
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id": id_lokasi_kantor}).mappings().all()


def get_range(mulai, selesai, id_pegawai=None):
    sql = text(f"""
        SELECT {_ABSENSI_COLS}
        FROM absensi a
        JOIN pegawai p ON p.id_pegawai = a.id_pegawai
        JOIN lokasi_kantor lk ON lk.id_lokasi_kantor = a.id_lokasi_kantor
        WHERE a.tanggal BETWEEN :mulai AND :selesai
          AND (CAST(:id_pegawai AS INTEGER) IS NULL OR a.id_pegawai = CAST(:id_pegawai AS INTEGER))
        ORDER BY a.tanggal DESC, p.full_name, a.jenis
    """)
    with get_engine().connect() as conn:
        params = {"mulai": mulai, "selesai": selesai, "id_pegawai": id_pegawai}
        return conn.execute(sql, params).mappings().all()


def get_by_id(id_absensi):
    sql = text(f"""
        SELECT {_ABSENSI_COLS}, a.photo_path
        FROM absensi a
        JOIN pegawai p ON p.id_pegawai = a.id_pegawai
        JOIN lokasi_kantor lk ON lk.id_lokasi_kantor = a.id_lokasi_kantor
        WHERE a.id_absensi = :id_absensi
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_absensi": id_absensi}).mappings().first()


def insert(data):
    """Kembalikan id_absensi, atau None jika sudah ada (UNIQUE pegawai+tanggal+jenis; aman dari double submit)."""
    sql = text("""
        INSERT INTO absensi (id_pegawai, id_lokasi_kantor, tanggal, jenis, waktu_absen, latitude, longitude,
                             akurasi_gps, jarak_meter, skor_wajah, photo_path, jam_jadwal, terlambat_menit,
                             status, created_at)
        VALUES (:id_pegawai, :id_lokasi_kantor, :tanggal, :jenis, :waktu_absen, :latitude, :longitude,
                :akurasi_gps, :jarak_meter, :skor_wajah, :photo_path, :jam_jadwal, :terlambat_menit,
                :status, :now)
        ON CONFLICT ON CONSTRAINT uq_absensi_pegawai_tanggal_jenis DO NOTHING
        RETURNING id_absensi
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita()}).scalar()


_GAGAL_FIELDS = ("id_pegawai", "id_lokasi_kantor", "jenis", "source", "stage", "error_code", "error_message",
                 "latitude", "longitude", "akurasi_gps", "jarak_meter", "skor_wajah", "photo_path")


def insert_gagal(data):
    row = {k: data.get(k) for k in _GAGAL_FIELDS}
    row["detail"] = json.dumps(data["detail"]) if data.get("detail") is not None else None
    sql = text(f"""
        INSERT INTO absensi_gagal ({", ".join(_GAGAL_FIELDS)}, detail, created_at)
        VALUES ({", ".join(":" + k for k in _GAGAL_FIELDS)}, CAST(:detail AS JSONB), :now)
        RETURNING id_absensi_gagal
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**row, "now": get_wita()}).scalar()


def get_gagal_range(mulai, selesai, id_pegawai=None):
    # created_at di-cast ke tanggal WITA agar filter tidak bergeser di DB ber-zona UTC
    sql = text("""
        SELECT g.id_absensi_gagal, g.id_pegawai, p.full_name, g.id_lokasi_kantor, g.jenis, g.source, g.stage,
               g.error_code, g.error_message, g.latitude, g.longitude, g.akurasi_gps, g.jarak_meter,
               g.skor_wajah, (g.photo_path IS NOT NULL) AS has_photo, g.detail, g.created_at
        FROM absensi_gagal g
        JOIN pegawai p ON p.id_pegawai = g.id_pegawai
        WHERE (g.created_at AT TIME ZONE 'Asia/Makassar')::date BETWEEN :mulai AND :selesai
          AND (CAST(:id_pegawai AS INTEGER) IS NULL OR g.id_pegawai = CAST(:id_pegawai AS INTEGER))
        ORDER BY g.created_at DESC
        LIMIT 1000
    """)
    with get_engine().connect() as conn:
        params = {"mulai": mulai, "selesai": selesai, "id_pegawai": id_pegawai}
        return conn.execute(sql, params).mappings().all()


def get_gagal_photo(id_absensi_gagal):
    sql = text("SELECT photo_path FROM absensi_gagal WHERE id_absensi_gagal = :id")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id": id_absensi_gagal}).scalar()
