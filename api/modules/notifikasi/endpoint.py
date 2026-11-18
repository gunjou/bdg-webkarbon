# api/modules/notifikasi/endpoint.py
from flask_jwt_extended import get_jwt
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import notifikasi_out


@ns.route("")
class Notifikasi(Resource):
    @api_doc(ns, notifikasi_out)
    @permission_required(["perizinan.view_all", "surat.view", "surat.create"])
    @measure_execution_time
    def get(self):
        """Akses: perizinan.view_all / surat.view / surat.create. Jumlah & 5 terbaru: pengajuan izin/koreksi menunggu
        (tanpa milik sendiri) dan draft surat. Bagian tanpa akses = null. Untuk badge lonceng & surat di header."""
        claims = get_jwt()
        return success(service.ringkasan(set(claims.get("permissions", [])), claims.get("id_pegawai")))
