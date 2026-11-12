# api/modules/absensi/__init__.py
# Dua namespace = dua grup Swagger, dipisah per aplikasi pemakai:
#   ns      → /absensi       aplikasi ADMIN (rekap & log, hanya baca)
#   ns_saya → /absensi/saya  aplikasi ABSEN (pegawai menandai hadir untuk dirinya sendiri)
from flask_restx import Namespace

ns = Namespace("absensi", description="[Aplikasi ADMIN] Rekap absensi semua pegawai & log absen gagal")
ns_saya = Namespace("absensi-saya", description="[Aplikasi ABSEN] Pegawai absen masuk/pulang untuk dirinya sendiri")

from . import endpoint  # noqa: E402,F401
