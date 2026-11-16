# api/modules/master/ref_options/endpoint.py
from flask import request
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import ref_option_input, ref_option_out, ref_option_parser

# daftar pilihan juga dibaca form penduduk & surat
READ_PERMS = ["ref_option.manage", "penduduk.view", "penduduk.manage", "surat.view", "surat.create"]


@ns.route("")
class RefOptionList(Resource):
    @api_doc(ns, ref_option_out, many=True)
    @ns.expect(ref_option_parser)
    @permission_required(READ_PERMS)
    @measure_execution_time
    def get(self):
        """Akses: ref_option.manage / penduduk.* / surat.view / surat.create. Daftar opsi, filter group_code."""
        args = ref_option_parser.parse_args()
        return success(service.list_all(args.get("group_code"), args.get("include_inactive") or 0))

    @api_doc(ns, ref_option_out, status=201, errors=(400, 401, 403, 422))
    @ns.expect(ref_option_input, validate=True)
    @permission_required("ref_option.manage")
    @measure_execution_time
    def post(self):
        """Akses: ref_option.manage. Tambah opsi."""
        data = service.create(request.get_json(), int(get_jwt_identity()))
        return success(data, "Opsi berhasil ditambahkan", 201)


@ns.route("/<int:id_ref_option>")
class RefOptionDetail(Resource):
    @api_doc(ns, ref_option_out, errors=(401, 403, 404))
    @permission_required("ref_option.manage")
    @measure_execution_time
    def get(self, id_ref_option):
        """Akses: ref_option.manage. Detail opsi."""
        return success(service.get(id_ref_option))

    @api_doc(ns, ref_option_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(ref_option_input, validate=True)
    @permission_required("ref_option.manage")
    @measure_execution_time
    def put(self, id_ref_option):
        """Akses: ref_option.manage. Ubah opsi (opsi bawaan: hanya label & urutan)."""
        data = service.update(id_ref_option, request.get_json(), int(get_jwt_identity()))
        return success(data, "Opsi berhasil diubah")

    @api_doc(ns, errors=(401, 403, 404, 422))
    @permission_required("ref_option.manage")
    @measure_execution_time
    def delete(self, id_ref_option):
        """Akses: ref_option.manage. Nonaktifkan opsi (opsi bawaan ditolak)."""
        service.deactivate(id_ref_option, int(get_jwt_identity()))
        return success(None, "Opsi berhasil dinonaktifkan")


@ns.route("/<int:id_ref_option>/activate")
class RefOptionActivate(Resource):
    @api_doc(ns, ref_option_out, errors=(401, 403, 404, 422))
    @permission_required("ref_option.manage")
    @measure_execution_time
    def post(self, id_ref_option):
        """Akses: ref_option.manage. Aktifkan kembali opsi."""
        return success(service.activate(id_ref_option, int(get_jwt_identity())), "Opsi berhasil diaktifkan")
