# api/modules/presensi/schema.py
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
gagal_input = ns.model("PresensiGagalInput", {
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
range_parser.add_argument("tanggal_mulai", type=str, location="args", help="YYYY-MM-DD, default awal bulan ini")
range_parser.add_argument("tanggal_selesai", type=str, location="args", help="YYYY-MM-DD, default hari ini")

# --- output ---
presensi_out = ns.model("Presensi", {
    "id_absensi": fields.Integer(example=101),
    "id_pegawai": fields.Integer(example=7),
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
    "jam_jadwal": fields.String(example="07:30", description="Snapshot jam jadwal"),
    "terlambat_menit": fields.Integer(example=0),
    "status": fields.String(enum=["tepat_waktu", "terlambat", "pulang_cepat"]),
    "is_koreksi": fields.Boolean(description="true = dikoreksi admin (tampilkan label Koreksi)"),
    "created_at": fields.DateTime(),
})

hari_ini_out = ns.model("PresensiHariIni", {
    "tanggal": fields.Date(),
    "waktu_server": fields.DateTime(description="Pakai ini, bukan jam HP"),
    "pegawai": fields.Nested(ns.model("PresensiPegawai", {
        "id_pegawai": fields.Integer(),
        "full_name": fields.String(),
        "face_enrolled": fields.Boolean(description="false = belum bisa absen"),
    })),
    "hari_kerja": fields.Boolean(),
    "kode": fields.String(description="Alasan bukan hari kerja: HOLIDAY / NOT_WORKDAY / NO_SCHEDULE"),
    "keterangan": fields.String(),
    "jadwal": fields.Nested(ns.model("PresensiJadwal", {
        "nama": fields.String(),
        "masuk": fields.String(example="07:30"),
        "pulang": fields.String(example="15:30"),
        "masuk_dibuka": fields.String(example="06:30"),
        "toleransi_terlambat_menit": fields.Integer(),
    }), allow_null=True, description="null jika bukan hari kerja"),
    "masuk": fields.Nested(presensi_out, allow_null=True, description="null = belum absen masuk"),
    "pulang": fields.Nested(presensi_out, allow_null=True, description="null = belum absen pulang"),
    "gps_max_akurasi_meter": fields.Float(example=50, description="Kirim absen hanya jika akurasi GPS HP <= nilai ini (meter)"),
})


# ======================================================
# PERIZINAN
# ======================================================
STATUS_IZIN = ["diajukan", "disetujui", "ditolak", "dibatalkan"]

# multipart/form-data agar lampiran bisa ikut
perizinan_parser = reqparse.RequestParser(bundle_errors=True)
perizinan_parser.add_argument("jenis_pengajuan", type=str, required=True, choices=["izin", "koreksi"], location="form")
perizinan_parser.add_argument("tanggal_mulai", type=str, required=True, location="form", help="YYYY-MM-DD")
perizinan_parser.add_argument("tanggal_selesai", type=str, location="form",
                              help="YYYY-MM-DD. izin: default = tanggal_mulai. koreksi: diabaikan")
perizinan_parser.add_argument("alasan", type=str, required=True, location="form")
perizinan_parser.add_argument("id_jenis_izin", type=int, location="form", help="Wajib untuk izin")
perizinan_parser.add_argument("jenis_absen", type=str, choices=JENIS, location="form", help="Wajib untuk koreksi")
perizinan_parser.add_argument("jam_koreksi", type=str, location="form", help="HH:MM, wajib untuk koreksi")
perizinan_parser.add_argument("lampiran", type=FileStorage, location="files",
                              help="Opsional (wajib jika jenis izin butuh_lampiran). jpg/png/pdf")

perizinan_filter = reqparse.RequestParser()
perizinan_filter.add_argument("status", type=str, choices=STATUS_IZIN, location="args")
perizinan_filter.add_argument("tahun", type=int, location="args", help="Tahun tanggal_mulai, mis. 2026")

jenis_izin_out = ns.model("PresensiJenisIzin", {
    "id_jenis_izin": fields.Integer(example=1),
    "code": fields.String(example="SAKIT"),
    "name": fields.String(example="Sakit"),
    "butuh_lampiran": fields.Integer(example=1, description="1 = lampiran wajib"),
    "dihitung_hadir": fields.Integer(example=0),
})

perizinan_out = ns.model("PresensiPerizinan", {
    "id_perizinan": fields.Integer(example=12),
    "id_pegawai": fields.Integer(),
    "jenis_pengajuan": fields.String(enum=["izin", "koreksi"]),
    "id_jenis_izin": fields.Integer(description="null untuk koreksi"),
    "jenis_izin_code": fields.String(example="SAKIT"),
    "jenis_izin_name": fields.String(example="Sakit"),
    "jenis_absen": fields.String(enum=JENIS, description="Hanya koreksi"),
    "tanggal_mulai": fields.Date(),
    "tanggal_selesai": fields.Date(),
    "jam_koreksi": fields.String(example="07:25", description="Hanya koreksi"),
    "alasan": fields.String(),
    "has_lampiran": fields.Boolean(description="true = ambil lewat /presensi/perizinan/{id}/lampiran"),
    "status": fields.String(enum=STATUS_IZIN),
    "reviewed_by": fields.Integer(),
    "reviewed_by_name": fields.String(),
    "reviewed_at": fields.DateTime(),
    "catatan_peninjau": fields.String(),
    "created_at": fields.DateTime(),
    "updated_at": fields.DateTime(),
})

hari_ini_out["izin"] = fields.Nested(perizinan_out, allow_null=True,
                                     description="Izin diajukan/disetujui yang mencakup hari ini; null = tidak ada")
