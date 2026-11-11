# api/modules/master/jadwal_kerja/__init__.py
from flask_restx import Namespace

ns = Namespace("master/jadwal-kerja", description="Master Jadwal Kerja (jam masuk/pulang per hari)")

from . import endpoint  # noqa: E402,F401
