# api/modules/master/lokasi_kantor/endpoint.py
from flask import request
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import lokasi_kantor_input, lokasi_kantor_out


@ns.route("")
class LokasiKantorList(Resource):
    @api_doc(ns, lokasi_kantor_out, many=True)
    @permission_required("lokasi_kantor.manage")
    @measure_execution_time
    def get(self):
        """Akses: lokasi_kantor.manage. Daftar lokasi kantor aktif."""
        return success(service.list_all())

    @api_doc(ns, lokasi_kantor_out, status=201, errors=(400, 401, 403, 422))
    @ns.expect(lokasi_kantor_input, validate=True)
    @permission_required("lokasi_kantor.manage")
    @measure_execution_time
    def post(self):
        """Akses: lokasi_kantor.manage. Tambah lokasi kantor."""
        data = service.create(request.get_json(), int(get_jwt_identity()))
        return success(data, "Lokasi kantor berhasil ditambahkan", 201)


@ns.route("/<int:id_lokasi_kantor>")
class LokasiKantorDetail(Resource):
    @api_doc(ns, lokasi_kantor_out, errors=(401, 403, 404))
    @permission_required("lokasi_kantor.manage")
    @measure_execution_time
    def get(self, id_lokasi_kantor):
        """Akses: lokasi_kantor.manage. Detail lokasi kantor."""
        return success(service.get(id_lokasi_kantor))

    @api_doc(ns, lokasi_kantor_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(lokasi_kantor_input, validate=True)
    @permission_required("lokasi_kantor.manage")
    @measure_execution_time
    def put(self, id_lokasi_kantor):
        """Akses: lokasi_kantor.manage. Ubah lokasi kantor."""
        data = service.update(id_lokasi_kantor, request.get_json(), int(get_jwt_identity()))
        return success(data, "Lokasi kantor berhasil diubah")

    @api_doc(ns, errors=(401, 403, 404, 422))
    @permission_required("lokasi_kantor.manage")
    @measure_execution_time
    def delete(self, id_lokasi_kantor):
        """Akses: lokasi_kantor.manage. Nonaktifkan lokasi kantor (ditolak jika masih dipakai pegawai aktif)."""
        service.deactivate(id_lokasi_kantor, int(get_jwt_identity()))
        return success(None, "Lokasi kantor berhasil dinonaktifkan")


@ns.route("/<int:id_lokasi_kantor>/activate")
class LokasiKantorActivate(Resource):
    @api_doc(ns, lokasi_kantor_out, errors=(401, 403, 404, 422))
    @permission_required("lokasi_kantor.manage")
    @measure_execution_time
    def post(self, id_lokasi_kantor):
        """Akses: lokasi_kantor.manage. Aktifkan kembali lokasi kantor."""
        return success(service.activate(id_lokasi_kantor, int(get_jwt_identity())), "Lokasi kantor berhasil diaktifkan")
