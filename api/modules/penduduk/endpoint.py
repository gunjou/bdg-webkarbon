# api/modules/penduduk/endpoint.py
from flask import request
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import penduduk_input, penduduk_out, penduduk_parser

# pencarian juga dipakai form pembuatan surat
READ_PERMS = ["penduduk.view", "penduduk.manage", "surat.create"]


@ns.route("")
class PendudukList(Resource):
    @api_doc(ns, penduduk_out, many=True)
    @ns.expect(penduduk_parser)
    @permission_required(READ_PERMS)
    @measure_execution_time
    def get(self):
        """Akses: penduduk.view / penduduk.manage / surat.create. Cari penduduk (NIK/KK/awalan nama), maks 200 baris."""
        return success(service.search(penduduk_parser.parse_args()))

    @api_doc(ns, penduduk_out, status=201, errors=(400, 401, 403, 422))
    @ns.expect(penduduk_input)  # tanpa validate: field opsional boleh null/"", divalidasi di service
    @permission_required("penduduk.manage")
    @measure_execution_time
    def post(self):
        """Akses: penduduk.manage. Tambah penduduk."""
        data = service.create(request.get_json(), int(get_jwt_identity()))
        return success(data, "Penduduk berhasil ditambahkan", 201)


@ns.route("/<int:id_penduduk>")
class PendudukDetail(Resource):
    @api_doc(ns, penduduk_out, errors=(401, 403, 404))
    @permission_required(READ_PERMS)
    @measure_execution_time
    def get(self, id_penduduk):
        """Akses: penduduk.view / penduduk.manage / surat.create. Detail penduduk (untuk isi otomatis form surat)."""
        return success(service.get(id_penduduk))

    @api_doc(ns, penduduk_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(penduduk_input)  # tanpa validate: field opsional boleh null/"", divalidasi di service
    @permission_required("penduduk.manage")
    @measure_execution_time
    def put(self, id_penduduk):
        """Akses: penduduk.manage. Ubah penduduk."""
        data = service.update(id_penduduk, request.get_json(), int(get_jwt_identity()))
        return success(data, "Penduduk berhasil diubah")

    @api_doc(ns, errors=(401, 403, 404))
    @permission_required("penduduk.manage")
    @measure_execution_time
    def delete(self, id_penduduk):
        """Akses: penduduk.manage. Nonaktifkan penduduk (pindah/meninggal)."""
        service.deactivate(id_penduduk, int(get_jwt_identity()))
        return success(None, "Penduduk berhasil dinonaktifkan")


@ns.route("/<int:id_penduduk>/activate")
class PendudukActivate(Resource):
    @api_doc(ns, penduduk_out, errors=(401, 403, 404, 422))
    @permission_required("penduduk.manage")
    @measure_execution_time
    def post(self, id_penduduk):
        """Akses: penduduk.manage. Aktifkan kembali penduduk."""
        return success(service.activate(id_penduduk, int(get_jwt_identity())), "Penduduk berhasil diaktifkan")
