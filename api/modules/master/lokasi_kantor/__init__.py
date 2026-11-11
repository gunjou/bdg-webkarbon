# api/modules/master/lokasi_kantor/__init__.py
from flask_restx import Namespace

ns = Namespace("master/lokasi-kantor", description="Master Lokasi Kantor (titik & radius absen sah)")

from . import endpoint  # noqa: E402,F401
