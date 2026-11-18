# api/modules/notifikasi/__init__.py
from flask_restx import Namespace

ns = Namespace("notifikasi", description="Ringkasan hal yang menunggu tindakan (lonceng & surat di header admin)")

from . import endpoint  # noqa: E402,F401
