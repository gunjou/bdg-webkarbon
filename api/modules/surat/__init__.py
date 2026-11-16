# api/modules/surat/__init__.py
from flask_restx import Namespace

ns = Namespace("surat", description="Surat keluar: draft, isian, lampiran, penandatangan, redaksi, preview")

from . import endpoint  # noqa: E402,F401
