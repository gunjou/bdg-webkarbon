# api/modules/presensi/__init__.py
# Aplikasi ABSEN: pegawai absen masuk/pulang untuk dirinya sendiri (pegawai diambil dari token).
from flask_restx import Namespace

ns = Namespace("presensi", description="[Aplikasi ABSEN] Pegawai absen masuk/pulang, riwayat & foto milik sendiri")

from . import endpoint  # noqa: E402,F401
