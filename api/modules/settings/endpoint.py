# api/modules/settings/endpoint.py
from flask import request, send_file
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc, file_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import logo_parser, posisi_parser, settings_input, settings_out

MANAGE = "settings.surat_manage"
READ_PERMS = [MANAGE, "surat.view", "surat.create", "jenis_surat.manage"]


@ns.route("")
class Settings(Resource):
    @api_doc(ns, settings_out)
    @permission_required(READ_PERMS)
    @measure_execution_time
    def get(self):
        """Akses: settings.surat_manage / surat.view / surat.create / jenis_surat.manage. Pengaturan desa & surat."""
        return success(service.get_all())

    @api_doc(ns, settings_out, errors=(400, 401, 403, 422))
    @ns.expect(settings_input)
    @permission_required(MANAGE)
    @measure_execution_time
    def put(self):
        """Akses: settings.surat_manage. Ubah sebagian/semua pengaturan (kirim hanya key yang diubah)."""
        return success(service.update(request.get_json(silent=True), int(get_jwt_identity())),
                       "Pengaturan berhasil disimpan")


@ns.route("/logo")
class SettingsLogo(Resource):
    @file_doc(ns, mimetype="image/png", errors=(401, 403))
    @ns.expect(posisi_parser)
    @permission_required(READ_PERMS)
    def get(self):
        """Akses: sama dengan GET /settings. Logo kop `posisi=kanan` (default, logo desa) /
        `kiri` (logo kabupaten): upload (image/png) atau bawaan (desa PNG, kabupaten SVG)."""
        path, mimetype = service.get_logo_file(posisi_parser.parse_args()["posisi"])
        return send_file(path, mimetype=mimetype)

    @api_doc(ns, settings_out, errors=(400, 401, 403, 413, 422))
    @ns.expect(logo_parser, posisi_parser)
    @permission_required(MANAGE)
    @measure_execution_time
    def post(self):
        """Akses: settings.surat_manage. Upload logo kop `?posisi=kanan|kiri` (png/jpg, disimpan PNG maks 600px).
        multipart/form-data."""
        logo = logo_parser.parse_args()["logo"]
        posisi = posisi_parser.parse_args()["posisi"]
        return success(service.set_logo(logo.read(), int(get_jwt_identity()), posisi), "Logo berhasil disimpan")
