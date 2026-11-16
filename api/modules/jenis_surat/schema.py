# api/modules/jenis_surat/schema.py
from flask_restx import fields, reqparse

from api.shared.docs import audit_fields
from . import ns

jenis_surat_parser = reqparse.RequestParser()
jenis_surat_parser.add_argument("include_inactive", type=int, choices=(0, 1), default=0, location="args")

SKEMA_EXAMPLE = {"sections": [
    {"key": "pemohon", "label": "Data Pemohon", "type": "penduduk",
     "tampilkan": ["nama", "ttl", "jenis_kelamin", "agama", "status_perkawinan", "pekerjaan", "kewarganegaraan",
                   "alamat"]},
    {"key": "lainnya", "label": "Keperluan", "type": "fields",
     "fields": [{"key": "keperluan", "label": "Keperluan", "type": "text", "required": True, "register": True}]},
]}
SKEMA_DESC = ("{sections:[...]}. type: penduduk (tampilkan[]) | fields (fields[]) | daftar (columns[]) | teks_bebas. "
              "Field: key, label, type text|textarea|number|date|rupiah|select, required, register, "
              "options_group (code grup ref_options) atau options [..] untuk select. Section penduduk pertama = pemohon utama.")

persyaratan_item = ns.model("Persyaratan", {
    "nama": fields.String(required=True, example="KTP"),
    "wajib": fields.Integer(example=1, description="1 = wajib dilampirkan"),
})

jenis_surat_input = ns.model("JenisSuratInput", {
    "code": fields.String(required=True, min_length=1, max_length=30, example="SKBM",
                          description="Huruf/angka/_ ; disimpan HURUF BESAR; tidak bisa diubah bila sudah ada surat"),
    "name": fields.String(required=True, min_length=1, max_length=150, example="Surat Keterangan Belum Menikah"),
    "kode_klasifikasi": fields.String(required=True, min_length=1, max_length=30, example="148.1"),
    "skema_form": fields.Raw(required=True, example=SKEMA_EXAMPLE, description=SKEMA_DESC),
    "template_isi": fields.String(example="", description="HTML + {{ placeholder }}; kosong = redaksi standar"),
    "persyaratan": fields.List(fields.Nested(persyaratan_item)),
    "sort_order": fields.Integer(default=0, example=1),
})

duplikat_input = ns.model("JenisSuratDuplikatInput", {
    "code": fields.String(required=True, min_length=1, max_length=30, example="SKBM2"),
    "name": fields.String(required=True, min_length=1, max_length=150, example="Salinan Surat Keterangan Belum Menikah"),
})

placeholder_input = ns.model("PlaceholderInput", {
    "skema_form": fields.Raw(required=True, example=SKEMA_EXAMPLE),
})

placeholder_out = ns.model("Placeholder", {
    "token": fields.String(example="{{ keperluan }}"),
    "label": fields.String(example="Keperluan"),
    "group": fields.String(example="Keperluan", description="Nama section / 'Data Desa' / 'Surat'"),
})

_base = {
    "id_jenis_surat": fields.Integer(example=1),
    "code": fields.String(example="SKBM"),
    "name": fields.String(example="Surat Keterangan Belum Menikah"),
    "kode_klasifikasi": fields.String(example="148.1"),
    "persyaratan": fields.List(fields.Nested(persyaratan_item)),
    "versi": fields.Integer(example=1),
    "sort_order": fields.Integer(example=1),
    **audit_fields(),
}
jenis_surat_list_out = ns.model("JenisSuratRingkas", _base)
jenis_surat_out = ns.model("JenisSurat", {
    **_base,
    "skema_form": fields.Raw(example=SKEMA_EXAMPLE),
    "template_isi": fields.String(),
})

preview_input = ns.model("JenisSuratPreviewInput", {
    "name": fields.String(example="Surat Keterangan Belum Menikah"),
    "skema_form": fields.Raw(required=True, example=SKEMA_EXAMPLE),
    "template_isi": fields.String(example="", description="kosong = redaksi standar"),
})
