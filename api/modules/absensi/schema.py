# api/modules/absensi/schema.py
from flask_restx import fields, reqparse
from werkzeug.datastructures import FileStorage

from . import ns

JENIS = ["masuk", "pulang"]
CLIENT_STAGES = ["GPS", "CAMERA", "LOCATION", "FACE"]

# multipart/form-data: data GPS + foto selfie
absen_parser = reqparse.RequestParser(bundle_errors=True)
absen_parser.add_argument("jenis", type=str, required=True, choices=JENIS, location="form")
absen_parser.add_argument("latitude", type=float, required=True, location="form")
absen_parser.add_argument("longitude", type=float, required=True, location="form")
absen_parser.add_argument("akurasi_gps", type=float, required=True, location="form",
                          help="Akurasi GPS dari perangkat (meter)")
absen_parser.add_argument("foto", type=FileStorage, required=True, location="files", help="Foto selfie (jpg/png)")

# laporan gagal dari aplikasi (izin GPS ditolak, kamera error, dsb.)
gagal_client_input = ns.model("AbsensiGagalClient", {
    "jenis": fields.String(enum=JENIS),
    "stage": fields.String(required=True, enum=CLIENT_STAGES, example="GPS"),
    "error_code": fields.String(required=True, pattern=r"^[A-Z0-9_]{1,50}$", example="GPS_PERMISSION_DENIED"),
    "error_message": fields.String(max_length=500),
    "latitude": fields.Float(min=-90, max=90),
    "longitude": fields.Float(min=-180, max=180),
    "akurasi_gps": fields.Float(min=0),
    "detail": fields.Raw(description="Info tambahan (object), mis. versi app / model HP"),
})

range_parser = reqparse.RequestParser()
range_parser.add_argument("tanggal_mulai", type=str, location="args", help="YYYY-MM-DD, default hari ini")
range_parser.add_argument("tanggal_selesai", type=str, location="args", help="YYYY-MM-DD, default = tanggal_mulai")
range_parser.add_argument("id_pegawai", type=int, location="args")

# --- output ---
absensi_out = ns.model("Absensi", {
    "id_absensi": fields.Integer(example=101),
    "id_pegawai": fields.Integer(example=7),
    "full_name": fields.String(example="Budi Santoso"),
    "id_lokasi_kantor": fields.Integer(example=1),
    "lokasi_kantor_name": fields.String(example="Kantor Desa"),
    "tanggal": fields.Date(example="2026-11-11"),
    "jenis": fields.String(enum=JENIS),
    "waktu_absen": fields.DateTime(),
    "latitude": fields.Float(),
    "longitude": fields.Float(),
    "akurasi_gps": fields.Float(),
    "jarak_meter": fields.Float(description="Jarak ke titik kantor"),
    "skor_wajah": fields.Float(description="0-1, makin tinggi makin mirip"),
    "jam_jadwal": fields.String(example="07:30", description="Snapshot jam jadwal (HH:MM)"),
    "terlambat_menit": fields.Integer(example=0),
    "status": fields.String(enum=["tepat_waktu", "terlambat", "pulang_cepat"]),
    "created_at": fields.DateTime(),
})

lokasi_absen_out = ns.model("LokasiAbsen", {
    "id_lokasi_kantor": fields.Integer(),
    "name": fields.String(),
    "latitude": fields.Float(),
    "longitude": fields.Float(),
    "radius_meter": fields.Integer(),
})

status_hari_ini_out = ns.model("AbsensiHariIni", {
    "tanggal": fields.Date(),
    "waktu_server": fields.DateTime(description="Pakai ini, bukan jam HP"),
    "pegawai": fields.Nested(ns.model("AbsensiPegawaiRingkas", {
        "id_pegawai": fields.Integer(),
        "full_name": fields.String(),
        "face_enrolled": fields.Boolean(description="false = belum bisa absen"),
    })),
    "hari_kerja": fields.Boolean(),
    "kode": fields.String(description="Alasan bukan hari kerja: HOLIDAY / NOT_WORKDAY / NO_SCHEDULE"),
    "keterangan": fields.String(),
    "jadwal": fields.Nested(ns.model("AbsensiJadwalHariIni", {
        "nama": fields.String(),
        "masuk": fields.String(example="07:30"),
        "pulang": fields.String(example="15:30"),
        "masuk_dibuka": fields.String(example="06:30"),
        "toleransi_terlambat_menit": fields.Integer(),
    }), allow_null=True, description="null jika bukan hari kerja"),
    "masuk": fields.Nested(absensi_out, allow_null=True, description="null = belum absen masuk"),
    "pulang": fields.Nested(absensi_out, allow_null=True, description="null = belum absen pulang"),
    "lokasi": fields.List(fields.Nested(lokasi_absen_out)),
    "gps_max_akurasi_meter": fields.Float(example=50),
})

absensi_gagal_out = ns.model("AbsensiGagal", {
    "id_absensi_gagal": fields.Integer(),
    "id_pegawai": fields.Integer(),
    "full_name": fields.String(),
    "id_lokasi_kantor": fields.Integer(),
    "jenis": fields.String(enum=JENIS),
    "source": fields.String(enum=["client", "server"]),
    "stage": fields.String(enum=["GPS", "CAMERA", "LOCATION", "FACE", "SCHEDULE", "SYSTEM"]),
    "error_code": fields.String(example="OUTSIDE_RADIUS"),
    "error_message": fields.String(),
    "latitude": fields.Float(),
    "longitude": fields.Float(),
    "akurasi_gps": fields.Float(),
    "jarak_meter": fields.Float(),
    "skor_wajah": fields.Float(),
    "has_photo": fields.Boolean(description="true = ada foto, ambil lewat /absensi/gagal/{id}/foto"),
    "detail": fields.Raw(),
    "created_at": fields.DateTime(),
})
