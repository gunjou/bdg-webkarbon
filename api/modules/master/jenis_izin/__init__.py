# api/modules/master/jenis_izin/__init__.py
from flask_restx import Namespace

ns = Namespace("master/jenis-izin", description="Master Jenis Izin (sakit, cuti, dinas luar, ...)")

from . import endpoint  # noqa: E402,F401
