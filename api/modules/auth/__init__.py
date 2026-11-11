# api/modules/auth/__init__.py
from flask_restx import Namespace

ns = Namespace("auth", description="Authentication Module")

from . import endpoint  # noqa: E402,F401  (daftarkan route ke ns)
