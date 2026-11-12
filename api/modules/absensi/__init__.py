# api/modules/absensi/__init__.py
# Aplikasi ADMIN: monitoring & rekap presensi, log gagal, koreksi absen, review perizinan pegawai.
from flask_restx import Namespace

ns = Namespace("absensi", description="[Aplikasi ADMIN] Monitoring presensi, rekap, koreksi & review perizinan")

from . import endpoint  # noqa: E402,F401
