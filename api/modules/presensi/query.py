# api/modules/presensi/query.py
# absensi & absensi_gagal append-only: hanya INSERT & SELECT.
import json

from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita

_ABSENSI_COLS = """
    a.id_absensi, a.id_pegawai, a.id_lokasi_kantor, lk.name AS lokasi_kantor_name,
    a.tanggal, a.jenis, a.waktu_absen, a.latitude, a.longitude, a.akurasi_gps, a.jarak_meter,
    a.skor_wajah, a.jam_jadwal, a.terlambat_menit, a.status, a.created_at,
    -- koreksi = pembuat/pengubah terakhir bukan akun pegawai itu sendiri (sama dgn modul absensi)
    (COALESCE(a.updated_by, a.created_by) IS NOT NULL AND
     (SELECT u.id_pegawai FROM users u WHERE u.id_user = COALESCE(a.updated_by, a.created_by))
       IS DISTINCT FROM a.id_pegawai) AS is_koreksi
"""


def get_settings(keys):
    sql = text("SELECT key, value FROM settings WHERE key = ANY(:keys)")
    with get_engine().connect() as conn:
        return {r["key"]: r["value"] for r in conn.execute(sql, {"keys": list(keys)}).mappings()}


def get_context(id_user, tanggal):
    """Pegawai milik user + jadwal + nama hari libur aktif pada tanggal tsb."""
    sql = text("""
        SELECT p.id_pegawai, p.full_name, p.is_active, p.embedding, p.id_jadwal_kerja,
               jk.name AS jadwal_kerja_name, jk.jadwal_harian, jk.toleransi_terlambat_menit,
               (SELECT name FROM hari_libur WHERE tanggal = :tanggal AND is_active = 1) AS libur
        FROM users u
        JOIN pegawai p ON p.id_pegawai = u.id_pegawai
        LEFT JOIN jadwal_kerja jk ON jk.id_jadwal_kerja = p.id_jadwal_kerja AND jk.is_active = 1
        WHERE u.id_user = :id_user
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_user": id_user, "tanggal": tanggal}).mappings().first()


def get_lokasi_aktif():
    sql = text("""
        SELECT id_lokasi_kantor, name, latitude, longitude, radius_meter
        FROM lokasi_kantor WHERE is_active = 1 ORDER BY name
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql).mappings().all()


def get_range(id_pegawai, mulai, selesai):
    sql = text(f"""
        SELECT {_ABSENSI_COLS}
        FROM absensi a
        JOIN lokasi_kantor lk ON lk.id_lokasi_kantor = a.id_lokasi_kantor
        WHERE a.id_pegawai = :id_pegawai AND a.tanggal BETWEEN :mulai AND :selesai
        ORDER BY a.tanggal DESC, a.jenis
    """)
    with get_engine().connect() as conn:
        params = {"id_pegawai": id_pegawai, "mulai": mulai, "selesai": selesai}
        return conn.execute(sql, params).mappings().all()


def get_by_id(id_absensi):
    sql = text(f"""
        SELECT {_ABSENSI_COLS}, a.photo_path
        FROM absensi a
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
                             status, created_at, created_by)
        VALUES (:id_pegawai, :id_lokasi_kantor, :tanggal, :jenis, :waktu_absen, :latitude, :longitude,
                :akurasi_gps, :jarak_meter, :skor_wajah, :photo_path, :jam_jadwal, :terlambat_menit,
                :status, :now, :created_by)
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
    """)
    with get_engine().begin() as conn:
        conn.execute(sql, {**row, "now": get_wita()})


# ======================================================
# PERIZINAN (milik pegawai sendiri)
# ======================================================
_IZIN_COLS = """
    z.id_perizinan, z.id_pegawai, z.jenis_pengajuan, z.id_jenis_izin, ji.code AS jenis_izin_code,
    ji.name AS jenis_izin_name, z.jenis_absen, z.tanggal_mulai, z.tanggal_selesai, z.jam_koreksi, z.alasan,
    (z.lampiran_path IS NOT NULL) AS has_lampiran, z.status, z.reviewed_by,
    COALESCE(rp.full_name, ru.username) AS reviewed_by_name, z.reviewed_at, z.catatan_peninjau,
    z.created_at, z.updated_at
"""
_IZIN_FROM = """
    FROM perizinan z
    LEFT JOIN jenis_izin ji ON ji.id_jenis_izin = z.id_jenis_izin
    LEFT JOIN users ru ON ru.id_user = z.reviewed_by
    LEFT JOIN pegawai rp ON rp.id_pegawai = ru.id_pegawai
"""


def get_izin_aktif(id_pegawai, tanggal):
    """Izin (bukan koreksi) berstatus diajukan/disetujui yang mencakup tanggal; disetujui didahulukan."""
    sql = text(f"""
        SELECT {_IZIN_COLS} {_IZIN_FROM}
        WHERE z.id_pegawai = :id_pegawai AND z.jenis_pengajuan = 'izin'
          AND z.status IN ('diajukan', 'disetujui')
          AND :tanggal BETWEEN z.tanggal_mulai AND z.tanggal_selesai
        ORDER BY (z.status = 'disetujui') DESC, z.id_perizinan DESC
        LIMIT 1
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_pegawai": id_pegawai, "tanggal": tanggal}).mappings().first()


def count_izin_bentrok(id_pegawai, mulai, selesai):
    sql = text("""
        SELECT count(*) FROM perizinan
        WHERE id_pegawai = :id_pegawai AND jenis_pengajuan = 'izin'
          AND status IN ('diajukan', 'disetujui')
          AND tanggal_mulai <= :selesai AND tanggal_selesai >= :mulai
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_pegawai": id_pegawai, "mulai": mulai, "selesai": selesai}).scalar()


def count_koreksi_aktif(id_pegawai, tanggal, jenis_absen):
    sql = text("""
        SELECT count(*) FROM perizinan
        WHERE id_pegawai = :id_pegawai AND jenis_pengajuan = 'koreksi'
          AND status IN ('diajukan', 'disetujui')
          AND tanggal_mulai = :tanggal AND jenis_absen = :jenis_absen
    """)
    with get_engine().connect() as conn:
        params = {"id_pegawai": id_pegawai, "tanggal": tanggal, "jenis_absen": jenis_absen}
        return conn.execute(sql, params).scalar()


def insert_perizinan(data, id_user):
    sql = text("""
        INSERT INTO perizinan (id_pegawai, id_jenis_izin, jenis_pengajuan, jenis_absen, tanggal_mulai,
                               tanggal_selesai, jam_koreksi, alasan, lampiran_path, status, created_at, created_by)
        VALUES (:id_pegawai, :id_jenis_izin, :jenis_pengajuan, :jenis_absen, :tanggal_mulai,
                :tanggal_selesai, :jam_koreksi, :alasan, :lampiran_path, 'diajukan', :now, :id_user)
        RETURNING id_perizinan
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita(), "id_user": id_user}).scalar()


def get_perizinan_list(id_pegawai, status=None, tahun=None):
    sql = text(f"""
        SELECT {_IZIN_COLS} {_IZIN_FROM}
        WHERE z.id_pegawai = :id_pegawai
          AND (CAST(:status AS VARCHAR) IS NULL OR z.status = CAST(:status AS VARCHAR))
          AND (CAST(:tahun AS INTEGER) IS NULL OR EXTRACT(YEAR FROM z.tanggal_mulai) = CAST(:tahun AS INTEGER))
        ORDER BY z.created_at DESC
    """)
    with get_engine().connect() as conn:
        params = {"id_pegawai": id_pegawai, "status": status, "tahun": tahun}
        return conn.execute(sql, params).mappings().all()


def get_perizinan(id_perizinan):
    sql = text(f"SELECT {_IZIN_COLS}, z.lampiran_path {_IZIN_FROM} WHERE z.id_perizinan = :id")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id": id_perizinan}).mappings().first()


def batal_perizinan(id_perizinan, id_pegawai, id_user):
    """Hanya yang masih 'diajukan' & milik pegawai tsb. Kembalikan rowcount."""
    sql = text("""
        UPDATE perizinan SET status = 'dibatalkan', updated_at = :now, updated_by = :id_user
        WHERE id_perizinan = :id AND id_pegawai = :id_pegawai AND status = 'diajukan'
    """)
    with get_engine().begin() as conn:
        params = {"id": id_perizinan, "id_pegawai": id_pegawai, "now": get_wita(), "id_user": id_user}
        return conn.execute(sql, params).rowcount
