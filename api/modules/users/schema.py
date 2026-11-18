# api/modules/users/schema.py
from flask_restx import fields, reqparse

from . import ns

list_parser = reqparse.RequestParser()
list_parser.add_argument("include_inactive", type=int, location="args", default=0, choices=(0, 1))

user_create = ns.model("UserCreate", {
    "username": fields.String(required=True, min_length=3, max_length=50, example="budi"),
    "email": fields.String(max_length=150, example="budi@desa.id"),
    "password": fields.String(required=True, min_length=5, example="rahasia123"),
    "id_roles": fields.List(fields.Integer, required=True, min_items=1, example=[2]),
})

# password opsional: diisi = ganti password
user_update = ns.model("UserUpdate", {
    "username": fields.String(required=True, min_length=3, max_length=50, example="budi"),
    "email": fields.String(max_length=150, example="budi@desa.id"),
    "password": fields.String(min_length=5, example="rahasiabaru"),
})

user_roles_input = ns.model("UserRoles", {
    "id_roles": fields.List(fields.Integer, required=True, min_items=1, example=[2]),
})

# --- output ---
role_ref = ns.model("RoleRef", {
    "id_role": fields.Integer(example=5),
    "code": fields.String(example="PEGAWAI"),
    "name": fields.String(example="Pegawai"),
})

user_out = ns.model("User", {
    "id_user": fields.Integer(example=2),
    "id_pegawai": fields.Integer(description="null = akun non-pegawai"),
    "full_name": fields.String(description="nama pegawai; null untuk akun non-pegawai"),
    "username": fields.String(example="budi"),
    "email": fields.String(),
    "last_login_at": fields.DateTime(),
    "is_active": fields.Integer(example=1),
    "created_at": fields.DateTime(),
    "updated_at": fields.DateTime(),
    "roles": fields.List(fields.Nested(role_ref)),
})

user_detail_out = ns.clone("UserDetail", user_out, {
    "kode_pemulihan": fields.String(example="A1B2C3", description="Kode login cadangan 6 karakter"),
})
