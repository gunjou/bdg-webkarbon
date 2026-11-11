# api/modules/master/hari_libur/endpoint.py
from flask import request
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import hari_libur_input, hari_libur_out


@ns.route("")
class HariLiburList(Resource):
    @api_doc(ns, hari_libur_out, many=True)
    @ns.doc(params={"tahun": {"description": "Filter tahun, mis. 2026 (opsional)", "type": "integer"}})
    @permission_required("hari_libur.manage")
    @measure_execution_time
    def get(self):
        """Akses: hari_libur.manage. Daftar hari libur aktif, urut tanggal."""
        return success(service.list_all(request.args.get("tahun", type=int)))

    @api_doc(ns, hari_libur_out, status=201, errors=(400, 401, 403, 422))
    @ns.expect(hari_libur_input, validate=True)
    @permission_required("hari_libur.manage")
    @measure_execution_time
    def post(self):
        """Akses: hari_libur.manage. Tambah hari libur."""
        data = service.create(request.get_json(), int(get_jwt_identity()))
        return success(data, "Hari libur berhasil ditambahkan", 201)


@ns.route("/<int:id_hari_libur>")
class HariLiburDetail(Resource):
    @api_doc(ns, hari_libur_out, errors=(401, 403, 404))
    @permission_required("hari_libur.manage")
    @measure_execution_time
    def get(self, id_hari_libur):
        """Akses: hari_libur.manage. Detail hari libur."""
        return success(service.get(id_hari_libur))

    @api_doc(ns, hari_libur_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(hari_libur_input, validate=True)
    @permission_required("hari_libur.manage")
    @measure_execution_time
    def put(self, id_hari_libur):
        """Akses: hari_libur.manage. Ubah hari libur."""
        data = service.update(id_hari_libur, request.get_json(), int(get_jwt_identity()))
        return success(data, "Hari libur berhasil diubah")

    @api_doc(ns, errors=(401, 403, 404, 422))
    @permission_required("hari_libur.manage")
    @measure_execution_time
    def delete(self, id_hari_libur):
        """Akses: hari_libur.manage. Nonaktifkan hari libur."""
        service.deactivate(id_hari_libur, int(get_jwt_identity()))
        return success(None, "Hari libur berhasil dinonaktifkan")


@ns.route("/<int:id_hari_libur>/activate")
class HariLiburActivate(Resource):
    @api_doc(ns, hari_libur_out, errors=(401, 403, 404, 422))
    @permission_required("hari_libur.manage")
    @measure_execution_time
    def post(self, id_hari_libur):
        """Akses: hari_libur.manage. Aktifkan kembali hari libur."""
        return success(service.activate(id_hari_libur, int(get_jwt_identity())), "Hari libur berhasil diaktifkan")
