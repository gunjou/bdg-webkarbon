# api/modules/penduduk/__init__.py
from flask_restx import Namespace

ns = Namespace("penduduk", description="Data induk warga (sumber pencarian pemohon surat)")

from . import endpoint  # noqa: E402,F401
