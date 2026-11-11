# api/modules/master/jabatan/endpoint.py
from flask import request
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import jabatan_input, jabatan_out


@ns.route("")
class JabatanList(Resource):
    @api_doc(ns, jabatan_out, many=True)
    @permission_required("jabatan.manage")
    @measure_execution_time
    def get(self):
        """Akses: jabatan.manage. Daftar jabatan aktif."""
        return success(service.list_all())

    @api_doc(ns, jabatan_out, status=201, errors=(400, 401, 403, 422))
    @ns.expect(jabatan_input, validate=True)
    @permission_required("jabatan.manage")
    @measure_execution_time
    def post(self):
        """Akses: jabatan.manage. Tambah jabatan."""
        data = service.create(request.get_json(), int(get_jwt_identity()))
        return success(data, "Jabatan berhasil ditambahkan", 201)


@ns.route("/<int:id_jabatan>")
class JabatanDetail(Resource):
    @api_doc(ns, jabatan_out, errors=(401, 403, 404))
    @permission_required("jabatan.manage")
    @measure_execution_time
    def get(self, id_jabatan):
        """Akses: jabatan.manage. Detail jabatan."""
        return success(service.get(id_jabatan))

    @api_doc(ns, jabatan_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(jabatan_input, validate=True)
    @permission_required("jabatan.manage")
    @measure_execution_time
    def put(self, id_jabatan):
        """Akses: jabatan.manage. Ubah jabatan."""
        data = service.update(id_jabatan, request.get_json(), int(get_jwt_identity()))
        return success(data, "Jabatan berhasil diubah")

    @api_doc(ns, errors=(401, 403, 404, 422))
    @permission_required("jabatan.manage")
    @measure_execution_time
    def delete(self, id_jabatan):
        """Akses: jabatan.manage. Nonaktifkan jabatan (ditolak jika masih dipakai pegawai aktif)."""
        service.deactivate(id_jabatan, int(get_jwt_identity()))
        return success(None, "Jabatan berhasil dinonaktifkan")


@ns.route("/<int:id_jabatan>/activate")
class JabatanActivate(Resource):
    @api_doc(ns, jabatan_out, errors=(401, 403, 404, 422))
    @permission_required("jabatan.manage")
    @measure_execution_time
    def post(self, id_jabatan):
        """Akses: jabatan.manage. Aktifkan kembali jabatan."""
        return success(service.activate(id_jabatan, int(get_jwt_identity())), "Jabatan berhasil diaktifkan")
