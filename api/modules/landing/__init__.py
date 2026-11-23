from flask_restx import Namespace

ns = Namespace("landing", description="Konten website desa (karangbongkot.com): admin & publik")

from . import endpoint  # noqa: E402,F401
