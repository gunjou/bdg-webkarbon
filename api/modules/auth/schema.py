# api/modules/auth/schema.py
from flask_restx import fields

from . import ns

# password diisi password ATAU kode pemulihan (dicek di service)
login_model = ns.model("Login", {
    "username": fields.String(required=True, min_length=1, example="budi"),
    "password": fields.String(required=True, min_length=1, example="rahasia",
                              description="Password atau kode pemulihan"),
})

refresh_model = ns.model("Refresh", {
    "refresh_token": fields.String(required=True, min_length=1),
})

# --- output ---
auth_user_out = ns.model("AuthUser", {
    "id_user": fields.Integer(example=1),
    "id_pegawai": fields.Integer(description="null jika akun non-pegawai"),
    "username": fields.String(example="budi"),
    "email": fields.String(),
    "full_name": fields.String(description="Nama pegawai, null jika non-pegawai"),
    "photo_path": fields.String(),
    "roles": fields.List(fields.String, example=["PEGAWAI"]),
    "permissions": fields.List(fields.String, example=["absensi.self", "perizinan.self"]),
})

login_out = ns.model("LoginResult", {
    "access_token": fields.String(),
    "refresh_token": fields.String(),
    "user": fields.Nested(auth_user_out),
})

refresh_out = ns.model("RefreshResult", {
    "access_token": fields.String(),
})
