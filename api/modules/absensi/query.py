# api/modules/absensi/query.py

from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita

# absen = koreksi bila user pembuat/pengubah terakhir bukan akun pegawai itu sendiri
_KOREKSI = """
    (COALESCE(a.updated_by, a.created_by) IS NOT NULL AND
     (SELECT u.id_pegawai FROM users u WHERE u.id_user = COALESCE(a.updated_by, a.created_by))
       IS DISTINCT FROM a.id_pegawai)
"""
_ABSENSI_COLS = f"""
    a.id_absensi, a.id_pegawai, p.full_name, p.nip, a.id_lokasi_kantor, lk.name AS lokasi_kantor_name,
    a.tanggal, a.jenis, a.waktu_absen, a.latitude, a.longitude, a.akurasi_gps, a.jarak_meter,
    a.skor_wajah, a.jam_jadwal, a.terlambat_menit, a.status, (a.photo_path IS NOT NULL) AS has_photo,
    {_KOREKSI} AS is_koreksi, a.created_at, a.created_by, a.updated_at, a.updated_by
"""
_ABSENSI_FROM = """
    FROM absensi a
    JOIN pegawai p ON p.id_pegawai = a.id_pegawai
    LEFT JOIN lokasi_kantor lk ON lk.id_lokasi_kantor = a.id_lokasi_kantor
"""


# ---------------- presensi ----------------
def get_pegawai_aktif(id_pegawai=None):
    sql = text("""
        SELECT p.id_pegawai, p.full_name, p.nip, j.name AS jabatan_name,
               jk.jadwal_harian, jk.name AS jadwal_kerja_name, jk.toleransi_terlambat_menit
        FROM pegawai p
        JOIN jabatan j ON j.id_jabatan = p.id_jabatan
        LEFT JOIN jadwal_kerja jk ON jk.id_jadwal_kerja = p.id_jadwal_kerja AND jk.is_active = 1
        WHERE p.is_active = 1
          AND (CAST(:id AS INTEGER) IS NULL OR p.id_pegawai = CAST(:id AS INTEGER))
        ORDER BY p.full_name
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id": id_pegawai}).mappings().all()


def get_libur(mulai, selesai):
    sql = text("SELECT tanggal, name FROM hari_libur WHERE is_active = 1 AND tanggal BETWEEN :mulai AND :selesai")
    with get_engine().connect() as conn:
        return {r["tanggal"]: r["name"] for r in conn.execute(sql, {"mulai": mulai, "selesai": selesai}).mappings()}


def get_absensi_range(mulai, selesai, id_pegawai=None, status=None):
    sql = text(f"""
        SELECT {_ABSENSI_COLS} {_ABSENSI_FROM}
        WHERE a.tanggal BETWEEN :mulai AND :selesai
          AND (CAST(:id_pegawai AS INTEGER) IS NULL OR a.id_pegawai = CAST(:id_pegawai AS INTEGER))
          AND (CAST(:status AS VARCHAR) IS NULL OR a.status = CAST(:status AS VARCHAR))
        ORDER BY a.tanggal DESC, p.full_name, a.jenis
    """)
    with get_engine().connect() as conn:
        params = {"mulai": mulai, "selesai": selesai, "id_pegawai": id_pegawai, "status": status}
        return conn.execute(sql, params).mappings().all()


def get_absensi(id_absensi):
    sql = text(f"SELECT {_ABSENSI_COLS}, a.photo_path {_ABSENSI_FROM} WHERE a.id_absensi = :id")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id": id_absensi}).mappings().first()


def get_izin_range(mulai, selesai, status, id_pegawai=None):
    """Izin (bukan koreksi) dengan status dalam `status` yang beririsan dengan rentang."""
    sql = text("""
        SELECT z.id_perizinan, z.id_pegawai, z.tanggal_mulai, z.tanggal_selesai, z.status,
               ji.code AS jenis_izin_code, ji.name AS jenis_izin_name, ji.dihitung_hadir
        FROM perizinan z JOIN jenis_izin ji ON ji.id_jenis_izin = z.id_jenis_izin
        WHERE z.jenis_pengajuan = 'izin' AND z.status = ANY(:status)
          AND z.tanggal_mulai <= :selesai AND z.tanggal_selesai >= :mulai
          AND (CAST(:id_pegawai AS INTEGER) IS NULL OR z.id_pegawai = CAST(:id_pegawai AS INTEGER))
    """)
    with get_engine().connect() as conn:
        params = {"mulai": mulai, "selesai": selesai, "status": list(status), "id_pegawai": id_pegawai}
        return conn.execute(sql, params).mappings().all()


_UPSERT_KOREKSI = text("""
    INSERT INTO absensi (id_pegawai, tanggal, jenis, waktu_absen, jam_jadwal, terlambat_menit, status, created_at, created_by)
    VALUES (:id_pegawai, :tanggal, :jenis, :waktu_absen, :jam_jadwal, :terlambat_menit, :status, :now, :id_user)
    ON CONFLICT ON CONSTRAINT uq_absensi_pegawai_tanggal_jenis DO UPDATE
    SET waktu_absen = EXCLUDED.waktu_absen, jam_jadwal = EXCLUDED.jam_jadwal, terlambat_menit = EXCLUDED.terlambat_menit,
        status = EXCLUDED.status, updated_at = :now, updated_by = :id_user
    RETURNING id_absensi
""")


def upsert_koreksi(data, id_user):
    with get_engine().begin() as conn:
        return conn.execute(_UPSERT_KOREKSI, {**data, "now": get_wita(), "id_user": id_user}).scalar()


# ---------------- absensi gagal ----------------
def get_gagal_range(mulai, selesai, id_pegawai=None, error_code=None):
    # created_at di-cast ke tanggal WITA agar filter tidak bergeser di DB ber-zona UTC
    sql = text("""
        SELECT g.id_absensi_gagal, g.id_pegawai, p.full_name, g.id_lokasi_kantor, g.jenis, g.source, g.stage,
               g.error_code, g.error_message, g.latitude, g.longitude, g.akurasi_gps, g.jarak_meter,
               g.skor_wajah, (g.photo_path IS NOT NULL) AS has_photo, g.detail, g.created_at
        FROM absensi_gagal g
        JOIN pegawai p ON p.id_pegawai = g.id_pegawai
        WHERE (g.created_at AT TIME ZONE 'Asia/Makassar')::date BETWEEN :mulai AND :selesai
          AND (CAST(:id_pegawai AS INTEGER) IS NULL OR g.id_pegawai = CAST(:id_pegawai AS INTEGER))
          AND (CAST(:error_code AS VARCHAR) IS NULL OR g.error_code = CAST(:error_code AS VARCHAR))
        ORDER BY g.created_at DESC
        LIMIT 1000
    """)
    with get_engine().connect() as conn:
        params = {"mulai": mulai, "selesai": selesai, "id_pegawai": id_pegawai, "error_code": error_code}
        return conn.execute(sql, params).mappings().all()


def get_gagal_photo(id_absensi_gagal):
    sql = text("SELECT photo_path FROM absensi_gagal WHERE id_absensi_gagal = :id")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id": id_absensi_gagal}).scalar()


# ---------------- perizinan ----------------
_IZIN_COLS = """
    z.id_perizinan, z.id_pegawai, p.full_name, p.nip, z.jenis_pengajuan, z.id_jenis_izin,
    ji.code AS jenis_izin_code, ji.name AS jenis_izin_name, z.jenis_absen, z.tanggal_mulai, z.tanggal_selesai,
    z.jam_koreksi, z.alasan, (z.lampiran_path IS NOT NULL) AS has_lampiran, z.status, z.reviewed_by,
    COALESCE(rp.full_name, ru.username) AS reviewed_by_name, z.reviewed_at, z.catatan_peninjau,
    z.created_at, z.updated_at
"""
_IZIN_FROM = """
    FROM perizinan z
    JOIN pegawai p ON p.id_pegawai = z.id_pegawai
    LEFT JOIN jenis_izin ji ON ji.id_jenis_izin = z.id_jenis_izin
    LEFT JOIN users ru ON ru.id_user = z.reviewed_by
    LEFT JOIN pegawai rp ON rp.id_pegawai = ru.id_pegawai
"""


def get_perizinan_list(f):
    sql = text(f"""
        SELECT {_IZIN_COLS} {_IZIN_FROM}
        WHERE (CAST(:status AS VARCHAR) IS NULL OR z.status = CAST(:status AS VARCHAR))
          AND (CAST(:jenis_pengajuan AS VARCHAR) IS NULL OR z.jenis_pengajuan = CAST(:jenis_pengajuan AS VARCHAR))
          AND (CAST(:id_pegawai AS INTEGER) IS NULL OR z.id_pegawai = CAST(:id_pegawai AS INTEGER))
          AND z.tanggal_mulai <= :selesai AND z.tanggal_selesai >= :mulai
        ORDER BY z.created_at DESC
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, f).mappings().all()


def get_perizinan(id_perizinan):
    sql = text(f"SELECT {_IZIN_COLS}, z.lampiran_path {_IZIN_FROM} WHERE z.id_perizinan = :id")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id": id_perizinan}).mappings().first()


def review_perizinan(id_perizinan, status, catatan, id_user, koreksi=None):
    """Satu transaksi: ubah status (hanya jika masih 'diajukan') + catat absen koreksi bila disetujui.
    Kembalikan rowcount perizinan (0 = sudah tidak diajukan, tidak ada yang diubah)."""
    now = get_wita()
    sql = text("""
        UPDATE perizinan SET status = :status, catatan_peninjau = :catatan, reviewed_by = :id_user,
               reviewed_at = :now, updated_at = :now, updated_by = :id_user
        WHERE id_perizinan = :id AND status = 'diajukan'
    """)
    with get_engine().begin() as conn:
        params = {"id": id_perizinan, "status": status, "catatan": catatan, "id_user": id_user, "now": now}
        count = conn.execute(sql, params).rowcount
        if count and koreksi:
            conn.execute(_UPSERT_KOREKSI, {**koreksi, "now": now, "id_user": id_user})
        return count
