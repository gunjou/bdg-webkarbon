# api/modules/users/__init__.py
from flask_restx import Namespace

ns = Namespace("users", description="Users Module")

from . import endpoint  # noqa: E402,F401
