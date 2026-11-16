# api/modules/jenis_surat/endpoint.py
from io import BytesIO

from flask import request, send_file
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc, file_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import (duplikat_input, jenis_surat_input, jenis_surat_list_out, jenis_surat_out, jenis_surat_parser,
                     placeholder_input, placeholder_out, preview_input)

MANAGE = "jenis_surat.manage"
READ_PERMS = [MANAGE, "surat.view", "surat.create"]


def _uid():
    return int(get_jwt_identity())


@ns.route("")
class JenisSuratList(Resource):
    @api_doc(ns, jenis_surat_list_out, many=True)
    @ns.expect(jenis_surat_parser)
    @permission_required(READ_PERMS)
    @measure_execution_time
    def get(self):
        """Akses: jenis_surat.manage / surat.view / surat.create. Daftar jenis surat (tanpa skema & redaksi)."""
        return success(service.list_all(jenis_surat_parser.parse_args().get("include_inactive") or 0))

    @api_doc(ns, jenis_surat_out, status=201, errors=(400, 401, 403, 422))
    @ns.expect(jenis_surat_input, validate=True)
    @permission_required(MANAGE)
    @measure_execution_time
    def post(self):
        """Akses: jenis_surat.manage. Tambah jenis surat; template_isi kosong = redaksi standar."""
        return success(service.create(request.get_json(), _uid()), "Jenis surat berhasil ditambahkan", 201)


@ns.route("/placeholder")
class JenisSuratPlaceholder(Resource):
    @api_doc(ns, placeholder_out, many=True, errors=(400, 401, 403, 422))
    @ns.expect(placeholder_input, validate=True)
    @permission_required(MANAGE)
    @measure_execution_time
    def post(self):
        """Akses: jenis_surat.manage. Daftar placeholder untuk panel editor dari skema_form (boleh belum disimpan)."""
        return success(service.get_placeholders(request.get_json().get("skema_form")))


@ns.route("/preview")
class JenisSuratPreview(Resource):
    @file_doc(ns, mimetype="application/pdf", errors=(400, 401, 403, 422))
    @ns.expect(preview_input, validate=True)
    @permission_required(MANAGE)
    def post(self):
        """Akses: jenis_surat.manage. Preview PDF (langkah 4 wizard) dengan data contoh, watermark CONTOH."""
        pdf = service.preview(request.get_json())
        return send_file(BytesIO(pdf), mimetype="application/pdf", download_name="preview.pdf")


@ns.route("/<int:id_jenis_surat>")
class JenisSuratDetail(Resource):
    @api_doc(ns, jenis_surat_out, errors=(401, 403, 404))
    @permission_required(READ_PERMS)
    @measure_execution_time
    def get(self, id_jenis_surat):
        """Akses: jenis_surat.manage / surat.view / surat.create. Detail jenis surat (dengan skema & redaksi)."""
        return success(service.get(id_jenis_surat))

    @api_doc(ns, jenis_surat_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(jenis_surat_input, validate=True)
    @permission_required(MANAGE)
    @measure_execution_time
    def put(self, id_jenis_surat):
        """Akses: jenis_surat.manage. Ubah jenis surat; versi naik bila skema/redaksi berubah (berlaku untuk surat baru)."""
        return success(service.update(id_jenis_surat, request.get_json(), _uid()), "Jenis surat berhasil diubah")

    @api_doc(ns, errors=(401, 403, 404))
    @permission_required(MANAGE)
    @measure_execution_time
    def delete(self, id_jenis_surat):
        """Akses: jenis_surat.manage. Nonaktifkan jenis surat."""
        service.deactivate(id_jenis_surat, _uid())
        return success(None, "Jenis surat berhasil dinonaktifkan")


@ns.route("/<int:id_jenis_surat>/activate")
class JenisSuratActivate(Resource):
    @api_doc(ns, jenis_surat_out, errors=(401, 403, 404))
    @permission_required(MANAGE)
    @measure_execution_time
    def post(self, id_jenis_surat):
        """Akses: jenis_surat.manage. Aktifkan kembali jenis surat."""
        return success(service.activate(id_jenis_surat, _uid()), "Jenis surat berhasil diaktifkan")


@ns.route("/<int:id_jenis_surat>/duplikat")
class JenisSuratDuplikat(Resource):
    @api_doc(ns, jenis_surat_out, status=201, errors=(400, 401, 403, 404, 422))
    @ns.expect(duplikat_input, validate=True)
    @permission_required(MANAGE)
    @measure_execution_time
    def post(self, id_jenis_surat):
        """Akses: jenis_surat.manage. Salin skema, redaksi & persyaratan ke jenis surat baru (versi 1)."""
        data = service.duplicate(id_jenis_surat, request.get_json(), _uid())
        return success(data, "Jenis surat berhasil diduplikat", 201)
