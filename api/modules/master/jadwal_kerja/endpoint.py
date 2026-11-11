# api/modules/master/jadwal_kerja/endpoint.py
from flask import request
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import jadwal_kerja_input, jadwal_kerja_out


@ns.route("")
class JadwalKerjaList(Resource):
    @api_doc(ns, jadwal_kerja_out, many=True)
    @permission_required("jadwal_kerja.manage")
    @measure_execution_time
    def get(self):
        """Akses: jadwal_kerja.manage. Daftar jadwal kerja aktif."""
        return success(service.list_all())

    @api_doc(ns, jadwal_kerja_out, status=201, errors=(400, 401, 403, 422))
    @ns.expect(jadwal_kerja_input, validate=True)
    @permission_required("jadwal_kerja.manage")
    @measure_execution_time
    def post(self):
        """Akses: jadwal_kerja.manage. Tambah jadwal kerja."""
        data = service.create(request.get_json(), int(get_jwt_identity()))
        return success(data, "Jadwal kerja berhasil ditambahkan", 201)


@ns.route("/<int:id_jadwal_kerja>")
class JadwalKerjaDetail(Resource):
    @api_doc(ns, jadwal_kerja_out, errors=(401, 403, 404))
    @permission_required("jadwal_kerja.manage")
    @measure_execution_time
    def get(self, id_jadwal_kerja):
        """Akses: jadwal_kerja.manage. Detail jadwal kerja."""
        return success(service.get(id_jadwal_kerja))

    @api_doc(ns, jadwal_kerja_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(jadwal_kerja_input, validate=True)
    @permission_required("jadwal_kerja.manage")
    @measure_execution_time
    def put(self, id_jadwal_kerja):
        """Akses: jadwal_kerja.manage. Ubah jadwal kerja."""
        data = service.update(id_jadwal_kerja, request.get_json(), int(get_jwt_identity()))
        return success(data, "Jadwal kerja berhasil diubah")

    @api_doc(ns, errors=(401, 403, 404, 422))
    @permission_required("jadwal_kerja.manage")
    @measure_execution_time
    def delete(self, id_jadwal_kerja):
        """Akses: jadwal_kerja.manage. Nonaktifkan jadwal kerja (ditolak jika masih dipakai pegawai aktif)."""
        service.deactivate(id_jadwal_kerja, int(get_jwt_identity()))
        return success(None, "Jadwal kerja berhasil dinonaktifkan")


@ns.route("/<int:id_jadwal_kerja>/activate")
class JadwalKerjaActivate(Resource):
    @api_doc(ns, jadwal_kerja_out, errors=(401, 403, 404, 422))
    @permission_required("jadwal_kerja.manage")
    @measure_execution_time
    def post(self, id_jadwal_kerja):
        """Akses: jadwal_kerja.manage. Aktifkan kembali jadwal kerja."""
        return success(service.activate(id_jadwal_kerja, int(get_jwt_identity())), "Jadwal kerja berhasil diaktifkan")
