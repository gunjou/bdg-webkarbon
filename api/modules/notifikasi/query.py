# api/modules/notifikasi/query.py
"""Hanya baca (COUNT + beberapa baris terbaru). Tabel milik modul absensi & surat; SQL sendiri di sini agar
satu request ringan dan tidak terbatas limit daftar."""
from sqlalchemy import text

from api.core.database import get_engine

_IZIN = """
    FROM perizinan z
    JOIN pegawai p ON p.id_pegawai = z.id_pegawai
    LEFT JOIN jenis_izin ji ON ji.id_jenis_izin = z.id_jenis_izin
    WHERE z.status = 'diajukan'
      AND (CAST(:kecuali AS INTEGER) IS NULL OR z.id_pegawai <> CAST(:kecuali AS INTEGER))
"""


def perizinan_menunggu(kecuali_id_pegawai, limit):
    params = {"kecuali": kecuali_id_pegawai, "limit": limit}
    with get_engine().connect() as conn:
        jumlah = conn.execute(text("SELECT count(*) " + _IZIN), params).scalar_one()
        items = conn.execute(text("""
            SELECT z.id_perizinan, p.full_name, z.jenis_pengajuan, ji.name AS jenis_izin_name,
                   z.jenis_absen, z.tanggal_mulai, z.tanggal_selesai, z.created_at
        """ + _IZIN + " ORDER BY z.created_at DESC LIMIT :limit"), params).mappings().all()
    return jumlah, items


def surat_draft(limit):
    with get_engine().connect() as conn:
        jumlah = conn.execute(text("SELECT count(*) FROM surat WHERE status = 'draft'")).scalar_one()
        items = conn.execute(text("""
            SELECT id_surat, judul, nama_pemohon, created_at, updated_at
            FROM surat WHERE status = 'draft'
            ORDER BY COALESCE(updated_at, created_at) DESC LIMIT :limit
        """), {"limit": limit}).mappings().all()
    return jumlah, items
