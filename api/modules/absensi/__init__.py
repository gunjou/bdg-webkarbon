# api/modules/absensi/__init__.py
from flask_restx import Namespace

ns = Namespace("absensi", description="Absensi wajah + GPS")

from . import endpoint  # noqa: E402,F401
