# api/modules/absensi/schema.py
from flask_restx import fields, reqparse

from . import ns

JENIS = ["masuk", "pulang"]
STATUS_ABSEN = ["tepat_waktu", "terlambat", "pulang_cepat"]
STATUS_IZIN = ["diajukan", "disetujui", "ditolak", "dibatalkan"]
STATUS_HARI = ["hadir", "izin", "libur", "bukan_hari_kerja", "alpha", "belum_absen"]

# ---------------- input ----------------
harian_parser = reqparse.RequestParser()
harian_parser.add_argument("tanggal", type=str, location="args", help="YYYY-MM-DD, default hari ini")

range_parser = reqparse.RequestParser()
range_parser.add_argument("tanggal_mulai", type=str, location="args", help="YYYY-MM-DD, default hari ini")
range_parser.add_argument("tanggal_selesai", type=str, location="args", help="YYYY-MM-DD, default = tanggal_mulai")
range_parser.add_argument("id_pegawai", type=int, location="args")

absensi_parser = range_parser.copy()
absensi_parser.add_argument("status", type=str, choices=STATUS_ABSEN, location="args")

gagal_parser = range_parser.copy()
gagal_parser.add_argument("error_code", type=str, location="args", help="mis. FACE_NOT_MATCH")

rekap_parser = reqparse.RequestParser()
rekap_parser.add_argument("bulan", type=str, location="args", help="YYYY-MM, default bulan ini")
rekap_parser.add_argument("id_pegawai", type=int, location="args")

perizinan_parser = reqparse.RequestParser()
perizinan_parser.add_argument("status", type=str, choices=STATUS_IZIN + ["semua"], location="args",
                              help="Default diajukan (antrean review)")
perizinan_parser.add_argument("jenis_pengajuan", type=str, choices=["izin", "koreksi"], location="args")
perizinan_parser.add_argument("id_pegawai", type=int, location="args")
perizinan_parser.add_argument("tanggal_mulai", type=str, location="args", help="YYYY-MM-DD; filter irisan tanggal izin")
perizinan_parser.add_argument("tanggal_selesai", type=str, location="args", help="YYYY-MM-DD")

koreksi_input = ns.model("AbsensiKoreksiInput", {
    "id_pegawai": fields.Integer(required=True, example=7),
    "tanggal": fields.String(required=True, example="2026-11-12", description="YYYY-MM-DD, tidak boleh masa depan"),
    "jenis": fields.String(required=True, enum=JENIS),
    "jam": fields.String(required=True, example="07:30", description="HH:MM (WITA). Status & terlambat dihitung dari jadwal"),
})

review_input = ns.model("PerizinanReviewInput", {
    "status": fields.String(required=True, enum=["disetujui", "ditolak"]),
    "catatan_peninjau": fields.String(description="Wajib jika ditolak"),
})

# ---------------- output ----------------
absensi_out = ns.model("Absensi", {
    "id_absensi": fields.Integer(example=101),
    "id_pegawai": fields.Integer(example=7),
    "full_name": fields.String(example="Budi Santoso"),
    "nip": fields.String(),
    "id_lokasi_kantor": fields.Integer(description="null jika hasil koreksi"),
    "lokasi_kantor_name": fields.String(),
    "tanggal": fields.Date(),
    "jenis": fields.String(enum=JENIS),
    "waktu_absen": fields.DateTime(),
    "latitude": fields.Float(),
    "longitude": fields.Float(),
    "akurasi_gps": fields.Float(),
    "jarak_meter": fields.Float(),
    "skor_wajah": fields.Float(),
    "jam_jadwal": fields.String(example="07:30"),
    "terlambat_menit": fields.Integer(),
    "status": fields.String(enum=STATUS_ABSEN),
    "has_photo": fields.Boolean(description="false untuk absen hasil koreksi"),
    "is_koreksi": fields.Boolean(description="true = dibuat/diubah oleh akun selain pegawai itu"),
    "created_at": fields.DateTime(),
    "created_by": fields.Integer(),
    "updated_at": fields.DateTime(),
    "updated_by": fields.Integer(),
})

izin_ringkas_out = ns.model("AbsensiIzinRingkas", {
    "id_perizinan": fields.Integer(),
    "tanggal_mulai": fields.Date(),
    "tanggal_selesai": fields.Date(),
    "status": fields.String(enum=["diajukan", "disetujui"]),
    "jenis_izin_code": fields.String(example="SAKIT"),
    "jenis_izin_name": fields.String(example="Sakit"),
    "dihitung_hadir": fields.Integer(),
})

harian_out = ns.model("AbsensiHarian", {
    "tanggal": fields.Date(),
    "pegawai": fields.List(fields.Nested(ns.model("AbsensiHarianPegawai", {
        "id_pegawai": fields.Integer(),
        "full_name": fields.String(),
        "nip": fields.String(),
        "jabatan_name": fields.String(),
        "status_hari": fields.String(enum=STATUS_HARI),
        "keterangan": fields.String(description="Nama hari libur, jika ada"),
        "jadwal": fields.Raw(example={"masuk": "07:30", "pulang": "15:30"}, description="Jadwal pegawai hari itu; null = bukan hari kerja"),
        "masuk": fields.Nested(absensi_out, allow_null=True),
        "pulang": fields.Nested(absensi_out, allow_null=True),
        "izin": fields.Nested(izin_ringkas_out, allow_null=True, description="Izin diajukan/disetujui hari itu"),
    }))),
})

rekap_out = ns.model("AbsensiRekap", {
    "bulan": fields.String(example="2026-11"),
    "tanggal_mulai": fields.Date(),
    "tanggal_selesai": fields.Date(description="Akhir bulan, atau hari ini jika bulan berjalan"),
    "pegawai": fields.List(fields.Nested(ns.model("AbsensiRekapPegawai", {
        "id_pegawai": fields.Integer(),
        "full_name": fields.String(),
        "nip": fields.String(),
        "jabatan_name": fields.String(),
        "hari_kerja": fields.Integer(description="Hari kerja menurut jadwal, di luar hari libur"),
        "hadir": fields.Integer(),
        "terlambat": fields.Integer(description="Jumlah hari terlambat"),
        "terlambat_menit": fields.Integer(description="Total menit terlambat"),
        "pulang_cepat": fields.Integer(),
        "tanpa_masuk": fields.Integer(description="Hadir tapi tidak absen masuk"),
        "tanpa_pulang": fields.Integer(description="Hadir tapi tidak absen pulang (hari ini tidak dihitung)"),
        "izin": fields.Integer(description="Hari izin disetujui"),
        "izin_per_jenis": fields.Raw(example={"SAKIT": 2}),
        "alpha": fields.Integer(description="Hari kerja tanpa absen & tanpa izin disetujui"),
        "libur": fields.Integer(),
    }))),
})

gagal_out = ns.model("AbsensiGagal", {
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
    "has_photo": fields.Boolean(description="true = ambil lewat /absensi/gagal/{id}/foto"),
    "detail": fields.Raw(),
    "created_at": fields.DateTime(),
})

perizinan_out = ns.model("AbsensiPerizinan", {
    "id_perizinan": fields.Integer(),
    "id_pegawai": fields.Integer(),
    "full_name": fields.String(),
    "nip": fields.String(),
    "jenis_pengajuan": fields.String(enum=["izin", "koreksi"]),
    "id_jenis_izin": fields.Integer(),
    "jenis_izin_code": fields.String(),
    "jenis_izin_name": fields.String(),
    "jenis_absen": fields.String(enum=JENIS),
    "tanggal_mulai": fields.Date(),
    "tanggal_selesai": fields.Date(),
    "jam_koreksi": fields.String(example="07:25"),
    "alasan": fields.String(),
    "has_lampiran": fields.Boolean(description="true = ambil lewat /absensi/perizinan/{id}/lampiran"),
    "status": fields.String(enum=STATUS_IZIN),
    "reviewed_by": fields.Integer(),
    "reviewed_by_name": fields.String(),
    "reviewed_at": fields.DateTime(),
    "catatan_peninjau": fields.String(),
    "created_at": fields.DateTime(),
    "updated_at": fields.DateTime(),
})
