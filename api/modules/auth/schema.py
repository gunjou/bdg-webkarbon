# api/modules/auth/schema.py
from flask_restx import fields

from . import ns

# password diisi password ATAU kode pemulihan (dicek di service)
login_model = ns.model("Login", {
    "username": fields.String(required=True, min_length=1, example="budi"),
    "password": fields.String(required=True, min_length=1, example="rahasia",
                              description="Password atau kode pemulihan"),
    "client": fields.String(required=True, enum=["admin", "absensi"], example="admin",
                            description="Aplikasi asal login. Dikirim otomatis oleh frontend, bukan input user"),
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

pegawai_login_out = ns.model("PegawaiLogin", {
    "id_user": fields.Integer(example=5),
    "id_pegawai": fields.Integer(example=3),
    "username": fields.String(example="budi"),
    "full_name": fields.String(example="Budi"),
    "nip": fields.String(),
    "jabatan": fields.String(example="Kaur Umum"),
    "photo_path": fields.String(),
    "face_enrolled": fields.Boolean(description="false = belum bisa absen (wajah belum didaftarkan)"),
})

login_out = ns.model("LoginResult", {
    "access_token": fields.String(),
    "refresh_token": fields.String(),
    "client": fields.String(enum=["admin", "absensi"]),
    "user": fields.Raw(description="client=admin → AuthUser (roles & permissions untuk menu); "
                                   "client=absensi → PegawaiLogin"),
})

refresh_out = ns.model("RefreshResult", {
    "access_token": fields.String(),
})
