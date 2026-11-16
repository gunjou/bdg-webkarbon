# api/modules/penduduk/schema.py
from flask_restx import fields, reqparse

from api.shared.docs import audit_fields
from . import ns

penduduk_parser = reqparse.RequestParser()
penduduk_parser.add_argument("q", type=str, location="args",
                             help="Angka = awalan NIK / No. KK; selain itu = awalan nama")
penduduk_parser.add_argument("dusun", type=str, location="args", help="code DUSUN")
penduduk_parser.add_argument("include_inactive", type=int, choices=(0, 1), default=0, location="args")
penduduk_parser.add_argument("limit", type=int, default=50, location="args", help="maks 200")
penduduk_parser.add_argument("offset", type=int, default=0, location="args")

_nomor = dict(min_length=16, max_length=16, pattern=r"^[0-9]{16}$")

penduduk_input = ns.model("PendudukInput", {
    "nik": fields.String(example="5201010101010001", description="16 digit, opsional, unik", **_nomor),
    "no_kk": fields.String(example="5201010101010002", description="16 digit, opsional", **_nomor),
    "full_name": fields.String(required=True, min_length=1, max_length=150, example="Gugun Gunawan"),
    "tempat_lahir": fields.String(max_length=100, example="Karang Bongkot"),
    "tanggal_lahir": fields.String(example="1998-11-03", description="Format YYYY-MM-DD"),
    "jenis_kelamin": fields.String(enum=["L", "P"], example="L"),
    "agama": fields.String(max_length=50, example="ISLAM", description="code AGAMA"),
    "pekerjaan": fields.String(max_length=50, example="WIRASWASTA", description="code PEKERJAAN"),
    "status_perkawinan": fields.String(max_length=50, example="BELUM_KAWIN", description="code STATUS_PERKAWINAN"),
    "kewarganegaraan": fields.String(max_length=50, example="WNI", description="code KEWARGANEGARAAN, default WNI"),
    "dusun": fields.String(max_length=50, example="KARANG_BONGKOT", description="code DUSUN"),
    "rt": fields.String(max_length=3, pattern=r"^[0-9]{1,3}$", example="002"),
    "rw": fields.String(max_length=3, pattern=r"^[0-9]{1,3}$", example="001"),
    "alamat": fields.String(max_length=255, example="Jl. Raya Labuapi", description="detail opsional"),
})

penduduk_out = ns.model("Penduduk", {
    "id_penduduk": fields.Integer(example=1),
    "nik": fields.String(example="5201010101010001"),
    "no_kk": fields.String(example="5201010101010002"),
    "full_name": fields.String(example="Gugun Gunawan"),
    "tempat_lahir": fields.String(example="Karang Bongkot"),
    "tanggal_lahir": fields.Date(example="1998-11-03"),
    "jenis_kelamin": fields.String(example="L"),
    "agama": fields.String(example="ISLAM"),
    "pekerjaan": fields.String(example="WIRASWASTA"),
    "status_perkawinan": fields.String(example="BELUM_KAWIN"),
    "kewarganegaraan": fields.String(example="WNI"),
    "dusun": fields.String(example="KARANG_BONGKOT"),
    "rt": fields.String(example="002"),
    "rw": fields.String(example="001"),
    "alamat": fields.String(example="Jl. Raya Labuapi"),
    **audit_fields(),
})
