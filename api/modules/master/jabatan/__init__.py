# api/modules/master/jabatan/__init__.py
from flask_restx import Namespace

ns = Namespace("master/jabatan", description="Master Jabatan")

from . import endpoint  # noqa: E402,F401
