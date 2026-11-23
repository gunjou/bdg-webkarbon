# api/modules/surat/schema.py
from flask_restx import fields, reqparse
from werkzeug.datastructures import FileStorage

from . import ns

STATUS = ("draft", "diterbitkan", "dibatalkan")

surat_parser = reqparse.RequestParser()
surat_parser.add_argument("status", type=str, choices=STATUS, location="args")
surat_parser.add_argument("id_jenis_surat", type=int, location="args")
surat_parser.add_argument("tahun", type=int, location="args", help="tahun tanggal surat (draft: tahun dibuat)")
surat_parser.add_argument("q", type=str, location="args", help="Angka = awalan NIK pemohon; selain itu = awalan nama")
surat_parser.add_argument("limit", type=int, default=50, location="args", help="maks 200")
surat_parser.add_argument("offset", type=int, default=0, location="args")

DATA_DESC = ("Isian sesuai skema_form surat: field `fields` di level atas ({keperluan: ...}); section penduduk/daftar/"
             "teks_bebas di data[<key section>]. Orang: {id_penduduk?, nama, nik, no_kk, tempat_lahir, tanggal_lahir, "
             "jenis_kelamin L/P, agama, pekerjaan, status_perkawinan, kewarganegaraan, dusun, rt, rw, alamat}.")
DATA_EXAMPLE = {"pemohon": {"id_penduduk": None, "nama": "GUGUN JOFANDI", "nik": "5201010311980001",
                            "tempat_lahir": "Perampuan", "tanggal_lahir": "1998-11-03", "jenis_kelamin": "L",
                            "agama": "ISLAM", "status_perkawinan": "BELUM_KAWIN", "kewarganegaraan": "WNI",
                            "rt": "002"},
                "keperluan": "pengambilan rumah"}

surat_create = ns.model("SuratCreate", {
    "id_jenis_surat": fields.Integer(required=True, example=1),
    "data": fields.Raw(example=DATA_EXAMPLE, description=DATA_DESC + " Opsional saat membuat draft."),
})

class NullableInteger(fields.Integer):
    """Integer yang boleh null (validasi restx default menolak None)."""
    __schema_type__ = ["integer", "null"]


surat_update = ns.model("SuratUpdate", {
    "data": fields.Raw(required=True, example=DATA_EXAMPLE, description=DATA_DESC + " Dikirim lengkap (menimpa)."),
    "id_penandatangan": NullableInteger(example=1, description="id_pegawai dari GET /surat/penandatangan; null / tidak dikirim = belum dipilih"),
})

redaksi_input = ns.model("SuratRedaksiInput", {
    "redaksi": fields.String(required=True, description="HTML + {{ placeholder }} sesuai skema surat ini"),
})

lampiran_parser = reqparse.RequestParser()
lampiran_parser.add_argument("nama", type=str, location="form", required=True, help="mis. KTP")
lampiran_parser.add_argument("file", type=FileStorage, location="files", required=True, help="PDF/JPG/PNG")

lampiran_out = ns.model("SuratLampiran", {
    "id": fields.String(example="3f2a..."),
    "nama": fields.String(example="KTP"),
    "mimetype": fields.String(example="application/pdf"),
})

penandatangan_out = ns.model("Penandatangan", {
    "id_pegawai": fields.Integer(example=1),
    "full_name": fields.String(example="Kaharudin"),
    "nip": fields.String(),
    "id_jabatan": fields.Integer(example=2),
    "jabatan": fields.String(example="Sekretaris Desa"),
    "atas_nama": fields.Integer(example=1, description="1 = dicetak 'a.n. Kepala Desa'"),
})

_audit = {
    "created_at": fields.DateTime(), "created_by": fields.Integer(),
    "updated_at": fields.DateTime(), "updated_by": fields.Integer(),
}
_base = {
    "id_surat": fields.Integer(example=1),
    "id_jenis_surat": fields.Integer(example=1),
    "jenis_surat_code": fields.String(example="SKBM"),
    "jenis_surat_name": fields.String(example="Surat Keterangan Belum Menikah"),
    "judul": fields.String(example="Surat Keterangan Belum Menikah", description="salinan judul saat draft dibuat"),
    "id_penduduk": fields.Integer(),
    "nama_pemohon": fields.String(example="GUGUN JOFANDI"),
    "nik_pemohon": fields.String(),
    "id_surat_diganti": fields.Integer(),
    "status": fields.String(enum=list(STATUS), example="draft"),
    "nomor_surat": fields.String(example="148.1/100/KRB/2026"),
    "nomor_urut": fields.Integer(),
    "tanggal_surat": fields.Date(),
    "id_penandatangan": fields.Integer(),
    "redaksi_diubah": fields.Integer(example=0),
    "terkunci": fields.Boolean(example=False, description="true = scan arsip sudah di-upload"),
    **_audit,
}
surat_list_out = ns.model("SuratRingkas", _base)
surat_out = ns.model("Surat", {
    **_base,
    "versi_template": fields.Integer(example=1),
    "skema_form": fields.Raw(),
    "redaksi": fields.String(),
    "data": fields.Raw(example=DATA_EXAMPLE),
    "lampiran": fields.List(fields.Nested(lampiran_out)),
    "atas_nama": fields.Integer(example=1),
    "data_penandatangan": fields.Raw(description="snapshot saat terbit"),
    "diterbitkan_oleh": fields.Integer(),
    "diterbitkan_pada": fields.DateTime(),
    "alasan_batal": fields.String(),
    "riwayat": fields.Raw(description="[{aksi, oleh, pada, catatan}]"),
})

perbaiki_input = ns.model("SuratPerbaikiInput", {
    "catatan": fields.String(required=True, example="Salah tulis tempat lahir"),
    "data": fields.Raw(example=DATA_EXAMPLE, description="Isian lengkap baru; tidak dikirim = isian lama"),
    "id_penandatangan": fields.Integer(description="tidak dikirim = penandatangan lama"),
    "redaksi": fields.String(description="butuh surat.edit_redaksi; tidak dikirim = redaksi lama"),
})

batal_input = ns.model("SuratBatalInput", {
    "alasan": fields.String(required=True, example="Salah jenis surat"),
})

arsip_parser = reqparse.RequestParser()
arsip_parser.add_argument("file", type=FileStorage, location="files", required=True,
                          help="Scan surat bertanda tangan & berstempel (PDF/JPG/PNG)")

agenda_parser = reqparse.RequestParser()
agenda_parser.add_argument("tahun", type=int, location="args", help="default tahun ini")

register_parser = agenda_parser.copy()
register_parser.add_argument("id_jenis_surat", type=int, location="args", required=True)

_baris = {
    "no": fields.Integer(example=1),
    "id_surat": fields.Integer(example=1),
    "nomor_urut": fields.Integer(example=100),
    "nomor_surat": fields.String(example="148.1/100/KRB/2026"),
    "tanggal_surat": fields.Date(),
    "judul": fields.String(example="Surat Keterangan Belum Menikah"),
    "id_jenis_surat": fields.Integer(example=1),
    "jenis_surat_code": fields.String(example="SKBM"),
    "nama_pemohon": fields.String(example="GUGUN JOFANDI"),
    "nik_pemohon": fields.String(),
    "status": fields.String(enum=["diterbitkan", "dibatalkan"]),
    "alasan_batal": fields.String(),
    "penandatangan": fields.String(example="Kaharudin"),
    "diarsip": fields.Boolean(description="scan bertanda tangan sudah di-upload"),
    "id_surat_diganti": fields.Integer(), "nomor_diganti": fields.String(),
    "id_pengganti": fields.Integer(), "nomor_pengganti": fields.String(),
    "keterangan": fields.String(example="DIBATALKAN – Salah jenis surat; Diganti dengan 148.1/101/KRB/2026"),
}
agenda_baris = ns.model("AgendaBaris", _baris)
agenda_out = ns.model("BukuAgenda", {
    "tahun": fields.Integer(example=2026),
    "rows": fields.List(fields.Nested(agenda_baris)),
})
register_kolom = ns.model("RegisterKolom", {
    "key": fields.String(example="keperluan"), "label": fields.String(example="Keperluan"),
    "type": fields.String(example="text"),
})
register_out = ns.model("BukuRegister", {
    "tahun": fields.Integer(example=2026),
    "id_jenis_surat": fields.Integer(example=1),
    "jenis_surat_code": fields.String(example="SKBM"),
    "jenis_surat_name": fields.String(example="Surat Keterangan Belum Menikah"),
    "kolom": fields.List(fields.Nested(register_kolom), description='field "register": true di skema'),
    "rows": fields.List(fields.Nested(ns.clone("RegisterBaris", agenda_baris, {
        "kolom": fields.Raw(example={"keperluan": "pengambilan rumah"}, description="{key kolom: nilai}"),
    }))),
})
