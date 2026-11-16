# api/modules/surat/query.py
import json

from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita

LIST_COLUMNS = """s.id_surat, s.id_jenis_surat, js.code AS jenis_surat_code, js.name AS jenis_surat_name,
    s.judul, s.id_penduduk, s.nama_pemohon, s.nik_pemohon, s.id_surat_diganti, s.status, s.nomor_surat, s.nomor_urut,
    s.tanggal_surat, s.id_penandatangan, s.redaksi_diubah, s.arsip_path IS NOT NULL AS terkunci,
    s.created_at, s.created_by, s.updated_at, s.updated_by"""


def _riwayat(aksi, id_user, catatan=None):
    return json.dumps([{"aksi": aksi, "oleh": id_user, "pada": get_wita().isoformat(), "catatan": catatan}])


def search(f):
    """f: status | id_jenis_surat | tahun | nomor (awalan NIK) | nama (awalan, lower) | limit | offset."""
    sql = text(f"""
        SELECT {LIST_COLUMNS}
        FROM surat s JOIN jenis_surat js ON js.id_jenis_surat = s.id_jenis_surat
        WHERE (CAST(:status AS VARCHAR) IS NULL OR s.status = :status)
          AND (CAST(:id_jenis_surat AS INTEGER) IS NULL OR s.id_jenis_surat = :id_jenis_surat)
          AND (CAST(:tahun AS INTEGER) IS NULL
               OR extract(year FROM coalesce(s.tanggal_surat, s.created_at)) = :tahun)
          AND (CAST(:nomor AS VARCHAR) IS NULL OR s.nik_pemohon LIKE :nomor || '%')
          AND (CAST(:nama AS VARCHAR) IS NULL OR lower(s.nama_pemohon) LIKE :nama || '%')
        ORDER BY s.created_at DESC, s.id_surat DESC
        LIMIT :limit OFFSET :offset
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, f).mappings().all()


def get_by_id(id_surat):
    sql = text("""
        SELECT s.*, js.code AS jenis_surat_code, js.name AS jenis_surat_name, s.arsip_path IS NOT NULL AS terkunci
        FROM surat s JOIN jenis_surat js ON js.id_jenis_surat = s.id_jenis_surat
        WHERE s.id_surat = :id_surat
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_surat": id_surat}).mappings().first()


def get_penandatangan(id_pegawai=None):
    """Pegawai aktif dengan jabatan aktif can_sign = 1."""
    sql = text("""
        SELECT p.id_pegawai, p.full_name, p.nip, j.id_jabatan, j.name AS jabatan
        FROM pegawai p JOIN jabatan j ON j.id_jabatan = p.id_jabatan
        WHERE p.is_active = 1 AND j.is_active = 1 AND j.can_sign = 1
          AND (CAST(:id_pegawai AS INTEGER) IS NULL OR p.id_pegawai = :id_pegawai)
        ORDER BY j.sort_order, p.full_name
    """)
    with get_engine().connect() as conn:
        return conn.execute(sql, {"id_pegawai": id_pegawai}).mappings().all()


def insert_draft(row, id_user):
    sql = text("""
        INSERT INTO surat (id_jenis_surat, judul, id_penduduk, nama_pemohon, nik_pemohon, versi_template, skema_form,
                           redaksi, data, riwayat, created_at, created_by)
        VALUES (:id_jenis_surat, :judul, :id_penduduk, :nama_pemohon, :nik_pemohon, :versi_template,
                CAST(:skema_form AS JSONB), :redaksi, CAST(:data AS JSONB), CAST(:riwayat AS JSONB), :now, :id_user)
        RETURNING id_surat
    """)
    params = {**row, "skema_form": json.dumps(row["skema_form"]), "data": json.dumps(row["data"]),
              "riwayat": _riwayat("dibuat", id_user), "now": get_wita(), "id_user": id_user}
    with get_engine().begin() as conn:
        return conn.execute(sql, params).scalar()


def update_draft(id_surat, row, id_user):
    """Hanya status draft (guard di WHERE: aman dari balapan dengan terbitkan). rowcount 0 = bukan draft."""
    sql = text("""
        UPDATE surat SET id_penduduk = :id_penduduk, nama_pemohon = :nama_pemohon, nik_pemohon = :nik_pemohon,
               data = CAST(:data AS JSONB), id_penandatangan = :id_penandatangan, atas_nama = :atas_nama,
               updated_at = :now, updated_by = :id_user
        WHERE id_surat = :id_surat AND status = 'draft'
    """)
    params = {**row, "data": json.dumps(row["data"]), "id_surat": id_surat, "now": get_wita(), "id_user": id_user}
    with get_engine().begin() as conn:
        return conn.execute(sql, params).rowcount


def set_redaksi(id_surat, redaksi, diubah, aksi, id_user):
    sql = text("""
        UPDATE surat SET redaksi = :redaksi, redaksi_diubah = :diubah, riwayat = riwayat || CAST(:riwayat AS JSONB),
               updated_at = :now, updated_by = :id_user
        WHERE id_surat = :id_surat AND status = 'draft'
    """)
    params = {"id_surat": id_surat, "redaksi": redaksi, "diubah": diubah, "riwayat": _riwayat(aksi, id_user),
              "now": get_wita(), "id_user": id_user}
    with get_engine().begin() as conn:
        return conn.execute(sql, params).rowcount


def set_lampiran(id_surat, lampiran, aksi, catatan, id_user):
    """Hanya surat yang belum batal & belum diarsip."""
    sql = text("""
        UPDATE surat SET lampiran = CAST(:lampiran AS JSONB), riwayat = riwayat || CAST(:riwayat AS JSONB),
               updated_at = :now, updated_by = :id_user
        WHERE id_surat = :id_surat AND status <> 'dibatalkan' AND arsip_path IS NULL
    """)
    params = {"id_surat": id_surat, "lampiran": json.dumps(lampiran), "riwayat": _riwayat(aksi, id_user, catatan),
              "now": get_wita(), "id_user": id_user}
    with get_engine().begin() as conn:
        return conn.execute(sql, params).rowcount


# ---------------------------------------------------------------- transaksi penerbitan (conn dari begin())

def begin():
    """Transaksi tulis; commit otomatis bila blok selesai, rollback bila ada exception."""
    return get_engine().begin()


def lock(conn, id_surat):
    sql = text("""
        SELECT s.*, js.code AS jenis_surat_code, js.kode_klasifikasi
        FROM surat s JOIN jenis_surat js ON js.id_jenis_surat = s.id_jenis_surat
        WHERE s.id_surat = :id_surat
        FOR UPDATE OF s
    """)
    return conn.execute(sql, {"id_surat": id_surat}).mappings().first()


def next_nomor(conn, cakupan, tahun):
    """Counter hanya maju. Ikut rollback bila transaksi gagal (tidak ada nomor terbuang karena error teknis)."""
    sql = text("""
        INSERT INTO nomor_urut_surat (cakupan, tahun, nomor_terakhir, updated_at)
        VALUES (:cakupan, :tahun, 1, :now)
        ON CONFLICT (cakupan, tahun) DO UPDATE
           SET nomor_terakhir = nomor_urut_surat.nomor_terakhir + 1, updated_at = :now
        RETURNING nomor_terakhir
    """)
    return conn.execute(sql, {"cakupan": cakupan, "tahun": tahun, "now": get_wita()}).scalar()


def nomor_exists(conn, nomor_surat):
    sql = text("SELECT 1 FROM surat WHERE nomor_surat = :nomor_surat")
    return conn.execute(sql, {"nomor_surat": nomor_surat}).first() is not None


def set_terbit(conn, id_surat, row, id_user):
    sql = text("""
        UPDATE surat SET status = 'diterbitkan', nomor_surat = :nomor_surat, nomor_urut = :nomor_urut,
               tanggal_surat = :tanggal_surat, data = CAST(:data AS JSONB), data_penandatangan = CAST(:ttd AS JSONB),
               id_penandatangan = :id_penandatangan, atas_nama = :atas_nama, pdf_path = :pdf_path,
               diterbitkan_oleh = :id_user, diterbitkan_pada = :now, riwayat = riwayat || CAST(:riwayat AS JSONB),
               updated_at = :now, updated_by = :id_user
        WHERE id_surat = :id_surat
    """)
    conn.execute(sql, {**row, "data": json.dumps(row["data"]), "ttd": json.dumps(row["data_penandatangan"]),
                       "riwayat": _riwayat("diterbitkan", id_user, row["nomor_surat"]), "id_surat": id_surat,
                       "now": get_wita(), "id_user": id_user})


def set_perbaikan(conn, id_surat, row, catatan, id_user):
    sql = text("""
        UPDATE surat SET id_penduduk = :id_penduduk, nama_pemohon = :nama_pemohon, nik_pemohon = :nik_pemohon,
               data = CAST(:data AS JSONB), redaksi = :redaksi, redaksi_diubah = :redaksi_diubah,
               id_penandatangan = :id_penandatangan, atas_nama = :atas_nama, data_penandatangan = CAST(:ttd AS JSONB),
               pdf_path = :pdf_path, riwayat = riwayat || CAST(:riwayat AS JSONB), updated_at = :now, updated_by = :id_user
        WHERE id_surat = :id_surat
    """)
    conn.execute(sql, {**row, "data": json.dumps(row["data"]), "ttd": json.dumps(row["data_penandatangan"]),
                       "riwayat": _riwayat("diperbaiki", id_user, catatan), "id_surat": id_surat,
                       "now": get_wita(), "id_user": id_user})


def set_arsip(conn, id_surat, arsip_path, id_user):
    sql = text("""
        UPDATE surat SET arsip_path = :arsip_path, riwayat = riwayat || CAST(:riwayat AS JSONB),
               updated_at = :now, updated_by = :id_user
        WHERE id_surat = :id_surat
    """)
    conn.execute(sql, {"id_surat": id_surat, "arsip_path": arsip_path, "riwayat": _riwayat("diarsipkan", id_user),
                       "now": get_wita(), "id_user": id_user})


def set_batal(conn, id_surat, alasan, id_user):
    sql = text("""
        UPDATE surat SET status = 'dibatalkan', alasan_batal = :alasan, riwayat = riwayat || CAST(:riwayat AS JSONB),
               updated_at = :now, updated_by = :id_user
        WHERE id_surat = :id_surat
    """)
    conn.execute(sql, {"id_surat": id_surat, "alasan": alasan, "riwayat": _riwayat("dibatalkan", id_user, alasan),
                       "now": get_wita(), "id_user": id_user})


def add_riwayat(conn, id_surat, aksi, catatan, id_user):
    sql = text("UPDATE surat SET riwayat = riwayat || CAST(:riwayat AS JSONB) WHERE id_surat = :id_surat")
    conn.execute(sql, {"id_surat": id_surat, "riwayat": _riwayat(aksi, id_user, catatan)})


def find_pengganti(conn, id_surat):
    sql = text("SELECT id_surat FROM surat WHERE id_surat_diganti = :id_surat AND status <> 'dibatalkan' LIMIT 1")
    return conn.execute(sql, {"id_surat": id_surat}).scalar()


def insert_pengganti(conn, row, id_user):
    sql = text("""
        INSERT INTO surat (id_jenis_surat, judul, id_penduduk, nama_pemohon, nik_pemohon, id_surat_diganti,
                           versi_template, skema_form, redaksi, redaksi_diubah, data, id_penandatangan, atas_nama,
                           riwayat, created_at, created_by)
        VALUES (:id_jenis_surat, :judul, :id_penduduk, :nama_pemohon, :nik_pemohon, :id_surat_diganti,
                :versi_template, CAST(:skema_form AS JSONB), :redaksi, :redaksi_diubah, CAST(:data AS JSONB),
                :id_penandatangan, :atas_nama, CAST(:riwayat AS JSONB), :now, :id_user)
        RETURNING id_surat
    """)
    params = {**row, "skema_form": json.dumps(row["skema_form"]), "data": json.dumps(row["data"]),
              "riwayat": _riwayat("dibuat", id_user, f"Pengganti surat #{row['id_surat_diganti']}"),
              "now": get_wita(), "id_user": id_user}
    return conn.execute(sql, params).scalar()


# ---------------------------------------------------------------- buku agenda & register

def get_register(mulai, selesai, id_jenis_surat=None):
    """Semua surat bernomor (terbit & batal) pada rentang tanggal_surat, urut tanggal lalu waktu terbit."""
    sql = text("""
        SELECT s.id_surat, s.nomor_urut, s.nomor_surat, s.tanggal_surat, s.judul, s.id_jenis_surat,
               js.code AS jenis_surat_code, s.nama_pemohon, s.nik_pemohon, s.status, s.alasan_batal, s.data,
               s.data_penandatangan ->> 'nama' AS penandatangan, s.arsip_path IS NOT NULL AS diarsip,
               s.id_surat_diganti, lama.nomor_surat AS nomor_diganti,
               baru.id_surat AS id_pengganti, baru.nomor_surat AS nomor_pengganti
        FROM surat s
        JOIN jenis_surat js ON js.id_jenis_surat = s.id_jenis_surat
        LEFT JOIN surat lama ON lama.id_surat = s.id_surat_diganti
        LEFT JOIN LATERAL (
            SELECT b.id_surat, b.nomor_surat FROM surat b
            WHERE b.id_surat_diganti = s.id_surat AND b.status <> 'dibatalkan'
            ORDER BY b.id_surat DESC LIMIT 1
        ) baru ON true
        WHERE s.nomor_surat IS NOT NULL
          AND s.tanggal_surat BETWEEN :mulai AND :selesai
          AND (CAST(:id_jenis_surat AS INTEGER) IS NULL OR s.id_jenis_surat = :id_jenis_surat)
        ORDER BY s.tanggal_surat, s.diterbitkan_pada, s.id_surat
    """)
    with get_engine().connect() as conn:
        params = {"mulai": mulai, "selesai": selesai, "id_jenis_surat": id_jenis_surat}
        return conn.execute(sql, params).mappings().all()
