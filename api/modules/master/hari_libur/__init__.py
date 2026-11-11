# api/modules/master/hari_libur/__init__.py
from flask_restx import Namespace

ns = Namespace("master/hari-libur", description="Master Hari Libur")

from . import endpoint  # noqa: E402,F401
