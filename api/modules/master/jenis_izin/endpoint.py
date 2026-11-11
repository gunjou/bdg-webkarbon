# api/modules/master/jenis_izin/endpoint.py
from flask import request
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import jenis_izin_input, jenis_izin_out


@ns.route("")
class JenisIzinList(Resource):
    @api_doc(ns, jenis_izin_out, many=True)
    @permission_required("jenis_izin.manage")
    @measure_execution_time
    def get(self):
        """Akses: jenis_izin.manage. Daftar jenis izin aktif."""
        return success(service.list_all())

    @api_doc(ns, jenis_izin_out, status=201, errors=(400, 401, 403, 422))
    @ns.expect(jenis_izin_input, validate=True)
    @permission_required("jenis_izin.manage")
    @measure_execution_time
    def post(self):
        """Akses: jenis_izin.manage. Tambah jenis izin."""
        data = service.create(request.get_json(), int(get_jwt_identity()))
        return success(data, "Jenis izin berhasil ditambahkan", 201)


@ns.route("/<int:id_jenis_izin>")
class JenisIzinDetail(Resource):
    @api_doc(ns, jenis_izin_out, errors=(401, 403, 404))
    @permission_required("jenis_izin.manage")
    @measure_execution_time
    def get(self, id_jenis_izin):
        """Akses: jenis_izin.manage. Detail jenis izin."""
        return success(service.get(id_jenis_izin))

    @api_doc(ns, jenis_izin_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(jenis_izin_input, validate=True)
    @permission_required("jenis_izin.manage")
    @measure_execution_time
    def put(self, id_jenis_izin):
        """Akses: jenis_izin.manage. Ubah jenis izin."""
        data = service.update(id_jenis_izin, request.get_json(), int(get_jwt_identity()))
        return success(data, "Jenis izin berhasil diubah")

    @api_doc(ns, errors=(401, 403, 404, 422))
    @permission_required("jenis_izin.manage")
    @measure_execution_time
    def delete(self, id_jenis_izin):
        """Akses: jenis_izin.manage. Nonaktifkan jenis izin (ditolak jika masih ada pengajuan berstatus diajukan)."""
        service.deactivate(id_jenis_izin, int(get_jwt_identity()))
        return success(None, "Jenis izin berhasil dinonaktifkan")


@ns.route("/<int:id_jenis_izin>/activate")
class JenisIzinActivate(Resource):
    @api_doc(ns, jenis_izin_out, errors=(401, 403, 404, 422))
    @permission_required("jenis_izin.manage")
    @measure_execution_time
    def post(self, id_jenis_izin):
        """Akses: jenis_izin.manage. Aktifkan kembali jenis izin."""
        return success(service.activate(id_jenis_izin, int(get_jwt_identity())), "Jenis izin berhasil diaktifkan")
