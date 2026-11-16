# api/modules/master/ref_options/schema.py
from flask_restx import fields, reqparse

from api.shared.docs import audit_fields
from . import ns

CODE_PATTERN = r"^[A-Za-z0-9_]+$"

ref_option_parser = reqparse.RequestParser()
ref_option_parser.add_argument("group_code", type=str, location="args", help="mis. AGAMA; kosong = semua grup")
ref_option_parser.add_argument("include_inactive", type=int, choices=(0, 1), default=0, location="args")

ref_option_input = ns.model("RefOptionInput", {
    "group_code": fields.String(required=True, min_length=1, max_length=50, pattern=CODE_PATTERN, example="AGAMA",
                                description="Disimpan HURUF BESAR; tidak bisa diubah untuk opsi bawaan"),
    "code": fields.String(required=True, min_length=1, max_length=50, pattern=CODE_PATTERN, example="ISLAM",
                          description="Disimpan HURUF BESAR; tidak bisa diubah untuk opsi bawaan"),
    "label": fields.String(required=True, min_length=1, max_length=150, example="Islam"),
    "sort_order": fields.Integer(default=0, example=1),
})

ref_option_out = ns.model("RefOption", {
    "id_ref_option": fields.Integer(example=1),
    "group_code": fields.String(example="AGAMA"),
    "code": fields.String(example="ISLAM"),
    "label": fields.String(example="Islam"),
    "sort_order": fields.Integer(example=1),
    "is_system": fields.Integer(example=1, description="1 = opsi bawaan: kode tetap & tidak bisa dinonaktifkan"),
    **audit_fields(),
})
