# api/modules/notifikasi/schema.py
from flask_restx import fields

from . import ns

izin_item = ns.model("NotifikasiPerizinan", {
    "id_perizinan": fields.Integer(),
    "full_name": fields.String(),
    "jenis_pengajuan": fields.String(enum=["izin", "koreksi"]),
    "jenis_izin_name": fields.String(description="null untuk koreksi"),
    "jenis_absen": fields.String(description="masuk|pulang, untuk koreksi"),
    "tanggal_mulai": fields.Date(),
    "tanggal_selesai": fields.Date(),
    "created_at": fields.DateTime(),
})

surat_item = ns.model("NotifikasiSurat", {
    "id_surat": fields.Integer(),
    "judul": fields.String(),
    "nama_pemohon": fields.String(),
    "created_at": fields.DateTime(),
    "updated_at": fields.DateTime(),
})

notifikasi_out = ns.model("Notifikasi", {
    "perizinan": fields.Nested(ns.model("NotifikasiBagianIzin", {
        "jumlah": fields.Integer(example=3), "items": fields.List(fields.Nested(izin_item))}),
        allow_null=True, description="null = tanpa akses perizinan.view_all"),
    "surat": fields.Nested(ns.model("NotifikasiBagianSurat", {
        "jumlah": fields.Integer(example=2), "items": fields.List(fields.Nested(surat_item))}),
        allow_null=True, description="null = tanpa akses surat.view/surat.create"),
})
