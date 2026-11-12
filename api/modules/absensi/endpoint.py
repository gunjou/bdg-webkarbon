# api/modules/absensi/endpoint.py
from flask import request, send_file
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc, file_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, ns_saya, service
from .schema import absen_parser, absensi_gagal_out, absensi_out, gagal_client_input, range_parser, status_hari_ini_out


def _id_user():
    return int(get_jwt_identity())


# ======================================================
# APLIKASI ADMIN — manajemen (baca semua pegawai)
# ======================================================
@ns.route("")
class AbsensiList(Resource):
    @api_doc(ns, absensi_out, many=True, errors=(401, 403, 422))
    @ns.expect(range_parser)
    @permission_required("absensi.view_all")
    @measure_execution_time
    def get(self):
        """[ADMIN] Akses: absensi.view_all. Daftar absensi semua pegawai per rentang tanggal (default hari ini)."""
        return success(service.list_all(range_parser.parse_args()))


@ns.route("/<int:id_absensi>")
class AbsensiDetail(Resource):
    @api_doc(ns, absensi_out, errors=(401, 403, 404))
    @permission_required("absensi.view_all")
    @measure_execution_time
    def get(self, id_absensi):
        """[ADMIN] Akses: absensi.view_all. Detail absensi."""
        return success(service.get(id_absensi))


@ns.route("/<int:id_absensi>/foto")
class AbsensiFoto(Resource):
    @file_doc(ns)
    @permission_required("absensi.view_all")
    def get(self, id_absensi):
        """[ADMIN] Akses: absensi.view_all. Foto selfie absen (image/jpeg)."""
        return send_file(service.foto_path(id_absensi), mimetype="image/jpeg")


@ns.route("/gagal")
class AbsensiGagal(Resource):
    @api_doc(ns, absensi_gagal_out, many=True, errors=(401, 403, 422))
    @ns.expect(range_parser)
    @permission_required("absensi_gagal.view")
    @measure_execution_time
    def get(self):
        """[ADMIN] Akses: absensi_gagal.view. Log absen gagal per rentang tanggal (maks 1000 baris)."""
        return success(service.list_gagal(range_parser.parse_args()))


@ns.route("/gagal/<int:id_absensi_gagal>/foto")
class AbsensiGagalFoto(Resource):
    @file_doc(ns)
    @permission_required("absensi_gagal.view")
    def get(self, id_absensi_gagal):
        """[ADMIN] Akses: absensi_gagal.view. Foto percobaan absen yang wajahnya tidak cocok."""
        return send_file(service.foto_gagal_path(id_absensi_gagal), mimetype="image/jpeg")


# ======================================================
# APLIKASI ABSEN — pegawai, hanya data diri sendiri (dari token)
# ======================================================
@ns_saya.route("")
class AbsenSaya(Resource):
    @api_doc(ns_saya, absensi_out, status=201, errors=(400, 401, 403, 413, 422), description="Absen tercatat. 422 = ditolak aturan absen (lihat code)")
    @ns_saya.expect(absen_parser)
    @permission_required("absensi.self")
    @measure_execution_time
    def post(self):
        """[ABSEN] Akses: absensi.self. Absen masuk/pulang: GPS + foto selfie. multipart/form-data."""
        a = absen_parser.parse_args()
        data = service.absen(_id_user(), a["jenis"], a["latitude"], a["longitude"], a["akurasi_gps"],
                             a["foto"].read())
        return success(data, f"Absen {a['jenis']} berhasil", 201)


@ns_saya.route("/hari-ini")
class AbsensiHariIni(Resource):
    @api_doc(ns_saya, status_hari_ini_out)
    @permission_required("absensi.self")
    @measure_execution_time
    def get(self):
        """[ABSEN] Akses: absensi.self. Status absen hari ini: jadwal, sudah masuk/pulang, lokasi kantor."""
        return success(service.status_hari_ini(_id_user()))


@ns_saya.route("/riwayat")
class AbsensiRiwayat(Resource):
    @api_doc(ns_saya, absensi_out, many=True, errors=(401, 403, 422))
    @ns_saya.expect(range_parser)
    @permission_required("absensi.self")
    @measure_execution_time
    def get(self):
        """[ABSEN] Akses: absensi.self. Riwayat absensi sendiri (id_pegawai diabaikan)."""
        return success(service.riwayat_saya(_id_user(), range_parser.parse_args()))


@ns_saya.route("/<int:id_absensi>/foto")
class AbsensiFotoSaya(Resource):
    @file_doc(ns_saya)
    @permission_required("absensi.self")
    def get(self, id_absensi):
        """[ABSEN] Akses: absensi.self, hanya milik sendiri. Foto selfie absen (image/jpeg)."""
        return send_file(service.foto_path(id_absensi, _id_user()), mimetype="image/jpeg")


@ns_saya.route("/gagal")
class AbsensiGagalSaya(Resource):
    @api_doc(ns_saya, status=201, errors=(400, 401, 403, 422))
    @ns_saya.expect(gagal_client_input, validate=True)
    @permission_required("absensi.self")
    @measure_execution_time
    def post(self):
        """[ABSEN] Akses: absensi.self. Laporkan kegagalan dari aplikasi (izin GPS/kamera ditolak, dsb.)."""
        service.lapor_gagal_client(_id_user(), request.get_json())
        return success(None, "Kegagalan tercatat", 201)
