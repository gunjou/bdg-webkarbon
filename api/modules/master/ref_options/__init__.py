# api/modules/master/ref_options/__init__.py
from flask_restx import Namespace

ns = Namespace("master/ref-options", description="Daftar pilihan (agama, pekerjaan, dusun, ...) per group_code")

from . import endpoint  # noqa: E402,F401
