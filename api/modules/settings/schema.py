# api/modules/settings/schema.py
from flask_restx import fields, reqparse
from werkzeug.datastructures import FileStorage

from . import ns

_s = fields.String
settings_input = ns.model("SettingsInput", {
    "desa.nama": _s(example="Karang Bongkot"),
    "desa.kecamatan": _s(example="Labuapi"),
    "desa.kabupaten": _s(example="Lombok Barat"),
    "desa.alamat": _s(example="Jl. Raya Labuapi No. 1, Kode Pos 83361"),
    "desa.email": _s(example="desa@karangbongkot.id"),
    "desa.website": _s(example="karangbongkot.id"),
    "surat.kode_desa": _s(example="KRB"),
    "surat.format_nomor": _s(example="{klasifikasi}/{urut}/{kode_desa}/{tahun}",
                             description="Token: {klasifikasi} {urut} {kode_desa} {tahun}; {urut} wajib; {klasifikasi} wajib bila cakupan PER_JENIS"),
    "surat.cakupan_nomor": _s(enum=["GLOBAL", "PER_JENIS"], example="PER_JENIS"),
    "surat.ukuran_kertas": _s(enum=["F4", "A4"], example="F4"),
})

settings_out = ns.clone("Settings", settings_input, {
    "desa.logo_path": _s(example="settings/abc.png", description="Logo kanan; diubah lewat POST /settings/logo"),
    "desa.logo_kiri_path": _s(example="settings/def.png", description="Logo kiri; diubah lewat POST /settings/logo?posisi=kiri"),
})

logo_parser = reqparse.RequestParser()
logo_parser.add_argument("logo", type=FileStorage, location="files", required=True, help="Logo desa (png/jpg)")

posisi_parser = reqparse.RequestParser()
posisi_parser.add_argument("posisi", choices=("kiri", "kanan"), default="kanan", location="args",
                           help="kiri = logo kabupaten, kanan = logo desa")
