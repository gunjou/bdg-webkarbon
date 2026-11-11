# api/modules/master/jabatan/schema.py
from flask_restx import fields

from api.shared.docs import audit_fields
from . import ns

jabatan_input = ns.model("JabatanInput", {
    "name": fields.String(required=True, min_length=1, max_length=100, example="Kaur Keuangan"),
    "sort_order": fields.Integer(default=0, example=1, description="Urutan tampil (kecil = atas)"),
})

jabatan_out = ns.model("Jabatan", {
    "id_jabatan": fields.Integer(example=1),
    "name": fields.String(example="Kaur Keuangan"),
    "sort_order": fields.Integer(example=1),
    **audit_fields(),
})
