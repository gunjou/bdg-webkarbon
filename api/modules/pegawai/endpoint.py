# api/modules/pegawai/endpoint.py
from flask import request, send_file
from flask_jwt_extended import get_jwt, get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc, file_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import foto_parser, password_input, pegawai_create_parser, pegawai_out, pegawai_update


def _actor():
    return int(get_jwt_identity()), set(get_jwt().get("permissions", []))


def _read_foto(args):
    foto = args.get("foto")
    return foto.read() if foto else None


@ns.route("")
class PegawaiList(Resource):
    @api_doc(ns, pegawai_out, many=True)
    @permission_required("pegawai.view")
    @measure_execution_time
    def get(self):
        """Akses: pegawai.view. Daftar pegawai aktif beserta akun user."""
        return success(service.list_all())

    @api_doc(ns, pegawai_out, status=201, errors=(400, 401, 403, 413, 422))
    @ns.expect(pegawai_create_parser)
    @permission_required("pegawai.manage")
    @measure_execution_time
    def post(self):
        """Akses: pegawai.manage. Tambah pegawai + akun user (+ foto wajah opsional). multipart/form-data."""
        args = pegawai_create_parser.parse_args()
        data = service.create(args, _read_foto(args), *_actor())
        return success(data, "Pegawai berhasil ditambahkan", 201)


@ns.route("/<int:id_pegawai>")
class PegawaiDetail(Resource):
    @api_doc(ns, pegawai_out, errors=(401, 403, 404))
    @permission_required("pegawai.view")
    @measure_execution_time
    def get(self, id_pegawai):
        """Akses: pegawai.view. Detail pegawai beserta akun user."""
        return success(service.get(id_pegawai))

    @api_doc(ns, pegawai_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(pegawai_update, validate=True)
    @permission_required("pegawai.manage")
    @measure_execution_time
    def put(self, id_pegawai):
        """Akses: pegawai.manage. Ubah data umum pegawai + user; id_roles kosong = tidak diubah."""
        data = service.update(id_pegawai, request.get_json(), *_actor())
        return success(data, "Pegawai berhasil diubah")

    @api_doc(ns, errors=(401, 403, 404, 422))
    @permission_required("pegawai.manage")
    @measure_execution_time
    def delete(self, id_pegawai):
        """Akses: pegawai.manage. Nonaktifkan pegawai beserta akun user-nya."""
        service.deactivate(id_pegawai, *_actor())
        return success(None, "Pegawai berhasil dinonaktifkan")


@ns.route("/<int:id_pegawai>/activate")
class PegawaiActivate(Resource):
    @api_doc(ns, pegawai_out, errors=(401, 403, 404))
    @permission_required("pegawai.manage")
    @measure_execution_time
    def post(self, id_pegawai):
        """Akses: pegawai.manage. Aktifkan kembali pegawai beserta akun user-nya."""
        return success(service.activate(id_pegawai, *_actor()), "Pegawai berhasil diaktifkan")


@ns.route("/<int:id_pegawai>/foto")
class PegawaiFoto(Resource):
    @file_doc(ns)
    @permission_required("pegawai.view")
    def get(self, id_pegawai):
        """Akses: pegawai.view. Unduh foto wajah pegawai (image/jpeg)."""
        return send_file(service.get_foto_path(id_pegawai), mimetype="image/jpeg")

    @api_doc(ns, pegawai_out, errors=(400, 401, 403, 404, 413, 422))
    @ns.expect(foto_parser)
    @permission_required("pegawai.enroll_face")
    @measure_execution_time
    def put(self, id_pegawai):
        """Akses: pegawai.enroll_face. Ganti/tambah foto wajah untuk absensi. multipart/form-data."""
        args = foto_parser.parse_args()
        data = service.set_foto(id_pegawai, _read_foto(args), int(get_jwt_identity()))
        return success(data, "Foto wajah berhasil disimpan")


@ns.route("/<int:id_pegawai>/password")
class PegawaiPassword(Resource):
    @api_doc(ns, errors=(400, 401, 403, 404, 422))
    @ns.expect(password_input, validate=True)
    @permission_required("pegawai.manage")
    @measure_execution_time
    def put(self, id_pegawai):
        """Akses: pegawai.manage. Ganti password akun user pegawai."""
        service.set_password(id_pegawai, request.get_json()["password"], *_actor())
        return success(None, "Password berhasil diubah")
