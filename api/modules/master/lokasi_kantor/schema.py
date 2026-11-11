# api/modules/master/lokasi_kantor/schema.py
from flask_restx import fields

from api.shared.docs import audit_fields
from . import ns

lokasi_kantor_input = ns.model("LokasiKantorInput", {
    "name": fields.String(required=True, min_length=1, max_length=100, example="Kantor Desa Karang Bongkot"),
    "latitude": fields.Float(required=True, min=-90, max=90, example=-8.654321),
    "longitude": fields.Float(required=True, min=-180, max=180, example=116.123456),
    "radius_meter": fields.Integer(default=100, min=1, example=100, description="Radius absen sah (meter)"),
})

lokasi_kantor_out = ns.model("LokasiKantor", {
    "id_lokasi_kantor": fields.Integer(example=1),
    "name": fields.String(example="Kantor Desa Karang Bongkot"),
    "latitude": fields.Float(example=-8.654321),
    "longitude": fields.Float(example=116.123456),
    "radius_meter": fields.Integer(example=100),
    **audit_fields(),
})
