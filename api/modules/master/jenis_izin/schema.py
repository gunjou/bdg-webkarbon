# api/modules/master/jenis_izin/schema.py
from flask_restx import fields

from api.shared.docs import audit_fields
from . import ns

jenis_izin_input = ns.model("JenisIzinInput", {
    "code": fields.String(required=True, min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_]+$",
                          example="SAKIT", description="Huruf/angka/_ ; disimpan HURUF BESAR"),
    "name": fields.String(required=True, min_length=1, max_length=100, example="Sakit"),
    "butuh_lampiran": fields.Integer(default=0, min=0, max=1, example=1, description="1 = wajib lampiran"),
    "dihitung_hadir": fields.Integer(default=0, min=0, max=1, example=0, description="1 = dihitung hadir"),
})

jenis_izin_out = ns.model("JenisIzin", {
    "id_jenis_izin": fields.Integer(example=1),
    "code": fields.String(example="SAKIT"),
    "name": fields.String(example="Sakit"),
    "butuh_lampiran": fields.Integer(example=1),
    "dihitung_hadir": fields.Integer(example=0),
    **audit_fields(),
})
