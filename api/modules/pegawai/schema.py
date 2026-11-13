# api/modules/pegawai/schema.py
from flask_restx import fields, reqparse
from werkzeug.datastructures import FileStorage

from . import ns

# POST = multipart/form-data agar foto bisa ikut dikirim
pegawai_create_parser = reqparse.RequestParser(bundle_errors=True)
_form = dict(location="form")
pegawai_create_parser.add_argument("full_name", type=str, required=True, help="Nama lengkap", **_form)
pegawai_create_parser.add_argument("id_jabatan", type=int, required=True, **_form)
pegawai_create_parser.add_argument("id_jadwal_kerja", type=int, default=1, help="Default 1", **_form)
pegawai_create_parser.add_argument("nip", type=str, **_form)
pegawai_create_parser.add_argument("phone", type=str, **_form)
pegawai_create_parser.add_argument("username", type=str, required=True, help="Username login", **_form)
pegawai_create_parser.add_argument("email", type=str, **_form)
pegawai_create_parser.add_argument("password", type=str, required=True, help="Minimal 5 karakter", **_form)
pegawai_create_parser.add_argument("id_roles", type=int, action="append",
                                   help="Kosong = PEGAWAI. 1 SUPER_ADMIN, 2 ADMIN, 3 SEKDES, 4 KADES, 5 PEGAWAI",
                                   **_form)
pegawai_create_parser.add_argument("foto", type=FileStorage, location="files",
                                   help="Opsional. Foto wajah (jpg/png) untuk absensi")

foto_parser = reqparse.RequestParser()
foto_parser.add_argument("foto", type=FileStorage, location="files", required=True, help="Foto wajah (jpg/png)")

# PUT = JSON; data umum pegawai & user. id_roles kosong = tidak diubah. Password lewat /password
pegawai_update = ns.model("PegawaiUpdate", {
    "full_name": fields.String(required=True, min_length=1, max_length=150, example="Budi Santoso"),
    "id_jabatan": fields.Integer(required=True, example=1),
    "id_jadwal_kerja": fields.Integer(required=True, example=1),
    "nip": fields.String(max_length=30, example="198501012010011001"),
    "phone": fields.String(max_length=20, example="081234567890"),
    "username": fields.String(required=True, min_length=3, max_length=50, example="budi"),
    "email": fields.String(max_length=150, example="budi@desa.id"),
    "id_roles": fields.List(fields.Integer, min_items=1, example=[5], description="Isi untuk ganti role"),
})

password_input = ns.model("PegawaiPassword", {
    "password": fields.String(required=True, min_length=5, example="rahasiabaru"),
})

# --- output ---
pegawai_role_ref = ns.model("PegawaiRoleRef", {
    "id_role": fields.Integer(example=5),
    "code": fields.String(example="PEGAWAI"),
    "name": fields.String(example="Pegawai"),
})

pegawai_out = ns.model("Pegawai", {
    "id_pegawai": fields.Integer(example=7),
    "full_name": fields.String(example="Budi Santoso"),
    "nip": fields.String(),
    "phone": fields.String(),
    "photo_path": fields.String(description="Path internal; ambil gambar lewat GET /pegawai/{id}/foto"),
    "has_face": fields.Boolean(description="true = foto wajah sudah didaftarkan (bisa absen)"),
    "id_jabatan": fields.Integer(example=1),
    "jabatan_name": fields.String(example="Kaur Keuangan"),
    "id_jadwal_kerja": fields.Integer(example=1),
    "jadwal_kerja_name": fields.String(example="Jadwal Normal"),
    "is_active": fields.Integer(example=1),
    "created_at": fields.DateTime(),
    "updated_at": fields.DateTime(),
    "id_user": fields.Integer(example=3),
    "username": fields.String(example="budi"),
    "email": fields.String(),
    "user_is_active": fields.Integer(example=1),
    "last_login_at": fields.DateTime(),
    "roles": fields.List(fields.Nested(pegawai_role_ref)),
})
