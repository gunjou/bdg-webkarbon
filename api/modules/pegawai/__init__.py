# api/modules/pegawai/__init__.py
from flask_restx import Namespace

ns = Namespace("pegawai", description="Pegawai Module")

from . import endpoint  # noqa: E402,F401
