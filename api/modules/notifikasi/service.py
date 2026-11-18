# api/modules/notifikasi/service.py
"""Isi bagian sesuai permission akun; bagian tanpa akses = null (frontend menyembunyikan tombolnya).
- perizinan (perizinan.view_all): pengajuan izin/koreksi berstatus diajukan, KECUALI milik akun sendiri
  (tidak boleh meninjau pengajuan sendiri, jadi bukan tugas akun itu).
- surat (surat.view / surat.create): draft yang belum diterbitkan."""
from . import query

LIMIT = 5


def _boleh(perms, *izin):
    return "*" in perms or any(i in perms for i in izin)


def ringkasan(permissions, id_pegawai):
    out = {"perizinan": None, "surat": None}
    if _boleh(permissions, "perizinan.view_all"):
        jumlah, items = query.perizinan_menunggu(id_pegawai, LIMIT)
        out["perizinan"] = {"jumlah": jumlah, "items": items}
    if _boleh(permissions, "surat.view", "surat.create"):
        jumlah, items = query.surat_draft(LIMIT)
        out["surat"] = {"jumlah": jumlah, "items": items}
    return out
