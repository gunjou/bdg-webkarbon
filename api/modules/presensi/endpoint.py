# api/modules/presensi/endpoint.py
from flask import request, send_file
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc, file_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import (absen_parser, gagal_input, hari_ini_out, jenis_izin_out, perizinan_filter, perizinan_out,
                     perizinan_parser, presensi_out, range_parser)


def _id_user():
    return int(get_jwt_identity())


@ns.route("")
class PresensiAbsen(Resource):
    @api_doc(ns, presensi_out, status=201, errors=(400, 401, 403, 413, 422),
             description="Absen tercatat. 422 = ditolak aturan absen (lihat code)")
    @ns.expect(absen_parser)
    @permission_required("absensi.self")
    @measure_execution_time
    def post(self):
        """Akses: absensi.self. Absen masuk/pulang: GPS + foto selfie. multipart/form-data."""
        a = absen_parser.parse_args()
        data = service.absen(_id_user(), a["jenis"], a["latitude"], a["longitude"], a["akurasi_gps"],
                             a["foto"].read())
        return success(data, f"Absen {a['jenis']} berhasil", 201)


@ns.route("/hari-ini")
class PresensiHariIni(Resource):
    @api_doc(ns, hari_ini_out)
    @permission_required("absensi.self")
    @measure_execution_time
    def get(self):
        """Akses: absensi.self. Status absen hari ini: jadwal, sudah masuk/pulang, batas akurasi GPS."""
        return success(service.hari_ini(_id_user()))


@ns.route("/gagal")
class PresensiGagal(Resource):
    @api_doc(ns, status=201, errors=(400, 401, 403, 422))
    @ns.expect(gagal_input, validate=True)
    @permission_required("absensi.self")
    @measure_execution_time
    def post(self):
        """Akses: absensi.self. Laporkan kegagalan di HP (izin GPS/kamera ditolak, timeout, jaringan)."""
        service.lapor_gagal(_id_user(), request.get_json())
        return success(None, "Kegagalan tercatat", 201)


@ns.route("/riwayat")
class PresensiRiwayat(Resource):
    @api_doc(ns, presensi_out, many=True, errors=(401, 403, 422))
    @ns.expect(range_parser)
    @permission_required("absensi.self")
    @measure_execution_time
    def get(self):
        """Akses: absensi.self. Riwayat absen sendiri (default bulan berjalan, maks 62 hari)."""
        return success(service.riwayat(_id_user(), range_parser.parse_args()))


@ns.route("/<int:id_absensi>/foto")
class PresensiFoto(Resource):
    @file_doc(ns)
    @permission_required("absensi.self")
    def get(self, id_absensi):
        """Akses: absensi.self, hanya milik sendiri. Foto selfie absen (image/jpeg)."""
        return send_file(service.foto_path(_id_user(), id_absensi), mimetype="image/jpeg")


# ======================================================
# PERIZINAN — Akses: perizinan.self, hanya milik sendiri
# ======================================================
@ns.route("/jenis-izin")
class PresensiJenisIzin(Resource):
    @api_doc(ns, jenis_izin_out, many=True)
    @permission_required("perizinan.self")
    @measure_execution_time
    def get(self):
        """Akses: perizinan.self. Pilihan jenis izin aktif (untuk form pengajuan)."""
        return success(service.list_jenis_izin())


@ns.route("/perizinan")
class PresensiPerizinanList(Resource):
    @api_doc(ns, perizinan_out, many=True, errors=(400, 401, 403))
    @ns.expect(perizinan_filter)
    @permission_required("perizinan.self")
    @measure_execution_time
    def get(self):
        """Akses: perizinan.self. Daftar pengajuan sendiri (terbaru di atas)."""
        return success(service.list_perizinan(_id_user(), perizinan_filter.parse_args()))

    @api_doc(ns, perizinan_out, status=201, errors=(400, 401, 403, 404, 413, 422))
    @ns.expect(perizinan_parser)
    @permission_required("perizinan.self")
    @measure_execution_time
    def post(self):
        """Akses: perizinan.self. Ajukan izin / koreksi absen. multipart/form-data."""
        args = perizinan_parser.parse_args()
        lampiran = args.pop("lampiran", None)
        data = service.ajukan_perizinan(_id_user(), args, lampiran.read() if lampiran else None)
        return success(data, "Pengajuan berhasil dikirim", 201)


@ns.route("/perizinan/<int:id_perizinan>")
class PresensiPerizinanDetail(Resource):
    @api_doc(ns, perizinan_out, errors=(401, 403, 404))
    @permission_required("perizinan.self")
    @measure_execution_time
    def get(self, id_perizinan):
        """Akses: perizinan.self. Detail pengajuan sendiri (termasuk catatan peninjau)."""
        return success(service.get_perizinan(_id_user(), id_perizinan))


@ns.route("/perizinan/<int:id_perizinan>/batal")
class PresensiPerizinanBatal(Resource):
    @api_doc(ns, perizinan_out, errors=(401, 403, 404, 422))
    @permission_required("perizinan.self")
    @measure_execution_time
    def put(self, id_perizinan):
        """Akses: perizinan.self. Batalkan pengajuan yang masih berstatus diajukan."""
        return success(service.batal_perizinan(_id_user(), id_perizinan), "Pengajuan dibatalkan")


@ns.route("/perizinan/<int:id_perizinan>/lampiran")
class PresensiPerizinanLampiran(Resource):
    @file_doc(ns, mimetype="image/jpeg")
    @permission_required("perizinan.self")
    def get(self, id_perizinan):
        """Akses: perizinan.self. Unduh lampiran pengajuan sendiri (image/jpeg atau application/pdf)."""
        path, mimetype = service.lampiran_path(_id_user(), id_perizinan)
        return send_file(path, mimetype=mimetype)
