# api/modules/jenis_surat/__init__.py
from flask_restx import Namespace

ns = Namespace("jenis-surat", description="Cetakan surat: skema form + redaksi standar")

from . import endpoint  # noqa: E402,F401
