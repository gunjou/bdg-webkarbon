# api/modules/absensi/endpoint.py
from flask import request, send_file
from flask_jwt_extended import get_jwt, get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc, file_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import (absensi_out, absensi_parser, gagal_out, gagal_parser, harian_out, harian_parser, izin_admin_parser,
                     koreksi_input, perizinan_out, perizinan_parser, rekap_out, rekap_parser, review_input)


def _id_user():
    return int(get_jwt_identity())


# ---------------- presensi ----------------
@ns.route("/harian")
class AbsensiHarian(Resource):
    @api_doc(ns, harian_out, errors=(401, 403, 422))
    @ns.expect(harian_parser)
    @permission_required("absensi.view_all")
    @measure_execution_time
    def get(self):
        """Akses: absensi.view_all. Status semua pegawai aktif pada satu tanggal (default hari ini)."""
        return success(service.harian(harian_parser.parse_args()))


@ns.route("/rekap")
class AbsensiRekap(Resource):
    @api_doc(ns, rekap_out, errors=(401, 403, 422))
    @ns.expect(rekap_parser)
    @permission_required("absensi.view_all")
    @measure_execution_time
    def get(self):
        """Akses: absensi.view_all. Rekap bulanan per pegawai (hadir, terlambat, izin, alpha, ...)."""
        return success(service.rekap(rekap_parser.parse_args()))


@ns.route("")
class AbsensiList(Resource):
    @api_doc(ns, absensi_out, many=True, errors=(401, 403, 422))
    @ns.expect(absensi_parser)
    @permission_required("absensi.view_all")
    @measure_execution_time
    def get(self):
        """Akses: absensi.view_all. Daftar absen per rentang tanggal (default hari ini, maks 62 hari)."""
        return success(service.list_absensi(absensi_parser.parse_args()))


@ns.route("/<int:id_absensi>")
class AbsensiDetail(Resource):
    @api_doc(ns, absensi_out, errors=(401, 403, 404))
    @permission_required("absensi.view_all")
    @measure_execution_time
    def get(self, id_absensi):
        """Akses: absensi.view_all. Detail absen."""
        return success(service.get_absensi(id_absensi))


@ns.route("/<int:id_absensi>/foto")
class AbsensiFoto(Resource):
    @file_doc(ns)
    @permission_required("absensi.view_all")
    def get(self, id_absensi):
        """Akses: absensi.view_all. Foto selfie absen (image/jpeg)."""
        return send_file(service.foto_absensi(id_absensi), mimetype="image/jpeg")


@ns.route("/koreksi")
class AbsensiKoreksi(Resource):
    @api_doc(ns, absensi_out, errors=(400, 401, 403, 422))
    @ns.expect(koreksi_input, validate=True)
    @permission_required("absensi.koreksi")
    @measure_execution_time
    def put(self):
        """Akses: absensi.koreksi. Buat / timpa absen pegawai (per tanggal & jenis) dengan jam & status pilihan admin."""
        return success(service.koreksi(request.get_json(), _id_user()), "Absen berhasil dikoreksi")


# ---------------- absensi gagal ----------------
@ns.route("/gagal")
class AbsensiGagal(Resource):
    @api_doc(ns, gagal_out, many=True, errors=(401, 403, 422))
    @ns.expect(gagal_parser)
    @permission_required("absensi_gagal.view")
    @measure_execution_time
    def get(self):
        """Akses: absensi_gagal.view. Log absen gagal per rentang tanggal (maks 1000 baris)."""
        return success(service.list_gagal(gagal_parser.parse_args()))


@ns.route("/gagal/<int:id_absensi_gagal>/foto")
class AbsensiGagalFoto(Resource):
    @file_doc(ns)
    @permission_required("absensi_gagal.view")
    def get(self, id_absensi_gagal):
        """Akses: absensi_gagal.view. Foto percobaan absen yang wajahnya tidak cocok (image/jpeg)."""
        return send_file(service.foto_gagal(id_absensi_gagal), mimetype="image/jpeg")


# ---------------- perizinan ----------------
@ns.route("/perizinan")
class AbsensiPerizinanList(Resource):
    @api_doc(ns, perizinan_out, many=True, errors=(400, 401, 403, 422))
    @ns.expect(perizinan_parser)
    @permission_required("perizinan.view_all")
    @measure_execution_time
    def get(self):
        """Akses: perizinan.view_all. Daftar pengajuan semua pegawai (default status diajukan; status=semua)."""
        return success(service.list_perizinan(perizinan_parser.parse_args()))

    @api_doc(ns, perizinan_out, status=201, errors=(400, 401, 403, 413, 422))
    @ns.expect(izin_admin_parser)
    @permission_required("perizinan.review")
    @measure_execution_time
    def post(self):
        """Akses: perizinan.review. Tambah izin untuk pegawai (langsung disetujui). multipart/form-data."""
        args = izin_admin_parser.parse_args()
        lampiran = args.pop("lampiran", None)
        data = service.tambah_izin(args, lampiran.read() if lampiran else None, _id_user())
        return success(data, "Izin berhasil ditambahkan", 201)


@ns.route("/perizinan/<int:id_perizinan>")
class AbsensiPerizinanDetail(Resource):
    @api_doc(ns, perizinan_out, errors=(401, 403, 404))
    @permission_required("perizinan.view_all")
    @measure_execution_time
    def get(self, id_perizinan):
        """Akses: perizinan.view_all. Detail pengajuan."""
        return success(service.get_perizinan(id_perizinan))


@ns.route("/perizinan/<int:id_perizinan>/lampiran")
class AbsensiPerizinanLampiran(Resource):
    @file_doc(ns)
    @permission_required("perizinan.view_all")
    def get(self, id_perizinan):
        """Akses: perizinan.view_all. Unduh lampiran (image/jpeg atau application/pdf)."""
        path, mimetype = service.lampiran_perizinan(id_perizinan)
        return send_file(path, mimetype=mimetype)


@ns.route("/perizinan/<int:id_perizinan>/review")
class AbsensiPerizinanReview(Resource):
    @api_doc(ns, perizinan_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(review_input, validate=True)
    @permission_required("perizinan.review")
    @measure_execution_time
    def put(self, id_perizinan):
        """Akses: perizinan.review. Setujui/tolak. Koreksi disetujui -> absen tercatat otomatis."""
        data = service.review(id_perizinan, request.get_json(), _id_user(), get_jwt().get("id_pegawai"))
        return success(data, f"Pengajuan {data['status']}")
