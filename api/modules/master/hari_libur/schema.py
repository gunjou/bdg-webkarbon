# api/modules/master/hari_libur/schema.py
from flask_restx import fields

from api.shared.docs import audit_fields
from . import ns

JENIS = ["nasional", "cuti_bersama", "lokal"]

hari_libur_input = ns.model("HariLiburInput", {
    "tanggal": fields.String(required=True, example="2026-12-25", description="Format YYYY-MM-DD"),
    "name": fields.String(required=True, min_length=1, max_length=150, example="Hari Raya Natal"),
    "jenis": fields.String(default="nasional", enum=JENIS, example="nasional"),
})

hari_libur_out = ns.model("HariLibur", {
    "id_hari_libur": fields.Integer(example=1),
    "tanggal": fields.Date(example="2026-12-25"),
    "name": fields.String(example="Hari Raya Natal"),
    "jenis": fields.String(enum=JENIS, example="nasional"),
    **audit_fields(),
})
