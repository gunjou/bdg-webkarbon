# api/modules/settings/__init__.py
from flask_restx import Namespace

ns = Namespace("settings", description="Pengaturan desa (kop surat) & persuratan")

from . import endpoint  # noqa: E402,F401
