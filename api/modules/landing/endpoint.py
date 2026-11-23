# api/modules/landing/endpoint.py
from flask import request, send_file
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc, file_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import (berita_input, berita_out, berita_parser, berita_ringkas_out, gambar_out, gambar_parser,
                     konten_model, perangkat_input, perangkat_out, potensi_input, potensi_out, publik_berita_parser,
                     publik_out)

MANAGE = "landing.manage"
PUBLIK = {"security": []}  # tanpa token


def _uid():
    return int(get_jwt_identity())


# ================================================================ admin
@ns.route("/konten")
class Konten(Resource):
    @api_doc(ns, konten_model)
    @permission_required(MANAGE)
    @measure_execution_time
    def get(self):
        """Akses: landing.manage. Konten website (hero, sekilas, sejarah, visi-misi, wilayah, statistik, kontak)."""
        return success(service.get_konten())

    @api_doc(ns, konten_model, errors=(400, 401, 403, 422))
    @ns.expect(konten_model)
    @permission_required(MANAGE)
    @measure_execution_time
    def put(self):
        """Akses: landing.manage. Simpan konten; kirim hanya bagian yang diubah (bagian lain tetap)."""
        return success(service.update_konten(request.get_json(silent=True), _uid()), "Konten website disimpan")


@ns.route("/gambar")
class Gambar(Resource):
    @api_doc(ns, gambar_out, status=201, errors=(400, 401, 403, 413, 422))
    @ns.expect(gambar_parser)
    @permission_required(MANAGE)
    @measure_execution_time
    def post(self):
        """Akses: landing.manage. Upload gambar (multipart, field `gambar`) → disimpan JPEG maks 1920px.
        URL publik: `/landing/publik/file/<path>`."""
        data = gambar_parser.parse_args()["gambar"].read()
        return success(service.upload_gambar(data), "Gambar berhasil diunggah", 201)


def _daftar_routes(jenis, path, model_in, model_out, label):
    """Route CRUD perangkat & potensi (bentuknya sama)."""

    class DaftarList(Resource):
        @api_doc(ns, model_out, many=True)
        @permission_required(MANAGE)
        @measure_execution_time
        def get(self):
            return success(service.daftar_list(jenis))

        @api_doc(ns, model_out, status=201, errors=(400, 401, 403, 422))
        @ns.expect(model_in, validate=True)
        @permission_required(MANAGE)
        @measure_execution_time
        def post(self):
            return success(service.daftar_create(jenis, request.get_json(), _uid()), f"{label} ditambahkan", 201)

    class DaftarDetail(Resource):
        @api_doc(ns, model_out, errors=(400, 401, 403, 404, 422))
        @ns.expect(model_in, validate=True)
        @permission_required(MANAGE)
        @measure_execution_time
        def put(self, id_):
            return success(service.daftar_update(jenis, id_, request.get_json(), _uid()), f"{label} diubah")

        @api_doc(ns, errors=(401, 403, 404))
        @permission_required(MANAGE)
        @measure_execution_time
        def delete(self, id_):
            service.daftar_delete(jenis, id_, _uid())
            return success(None, f"{label} dihapus")

    DaftarList.get.__doc__ = f"Akses: landing.manage. Daftar {label.lower()} aktif (urut `urutan`)."
    DaftarList.post.__doc__ = f"Akses: landing.manage. Tambah {label.lower()}."
    DaftarDetail.put.__doc__ = f"Akses: landing.manage. Ubah {label.lower()}."
    DaftarDetail.delete.__doc__ = f"Akses: landing.manage. Hapus {label.lower()} (soft delete)."
    DaftarList.__name__, DaftarDetail.__name__ = f"{jenis.title()}List", f"{jenis.title()}Detail"
    ns.route(f"/{path}")(DaftarList)
    ns.route(f"/{path}/<int:id_>")(DaftarDetail)


_daftar_routes("perangkat", "perangkat", perangkat_input, perangkat_out, "Perangkat desa")
_daftar_routes("potensi", "potensi", potensi_input, potensi_out, "Potensi")


@ns.route("/berita")
class BeritaList(Resource):
    @api_doc(ns, berita_ringkas_out, many=True, paged=True, errors=(400, 401, 403))
    @ns.expect(berita_parser)
    @permission_required(MANAGE)
    @measure_execution_time
    def get(self):
        """Akses: landing.manage. Daftar berita (draft & terbit), terbaru dulu; tanpa `isi`. meta: {total, limit, offset}."""
        a = berita_parser.parse_args()
        rows, meta = service.berita_list(a["status"], a["q"], a["limit"], a["offset"])
        return success(rows, meta=meta)

    @api_doc(ns, berita_out, status=201, errors=(400, 401, 403, 422))
    @ns.expect(berita_input, validate=True)
    @permission_required(MANAGE)
    @measure_execution_time
    def post(self):
        """Akses: landing.manage. Tambah berita."""
        return success(service.berita_create(request.get_json(), _uid()), "Berita ditambahkan", 201)


@ns.route("/berita/<int:id_berita>")
class BeritaDetail(Resource):
    @api_doc(ns, berita_out, errors=(401, 403, 404))
    @permission_required(MANAGE)
    @measure_execution_time
    def get(self, id_berita):
        """Akses: landing.manage. Detail berita (termasuk `isi`)."""
        return success(service.berita_get(id_berita))

    @api_doc(ns, berita_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(berita_input, validate=True)
    @permission_required(MANAGE)
    @measure_execution_time
    def put(self, id_berita):
        """Akses: landing.manage. Ubah berita (termasuk terbitkan / kembalikan ke draft)."""
        return success(service.berita_update(id_berita, request.get_json(), _uid()), "Berita diubah")

    @api_doc(ns, errors=(401, 403, 404))
    @permission_required(MANAGE)
    @measure_execution_time
    def delete(self, id_berita):
        """Akses: landing.manage. Hapus berita (soft delete)."""
        service.berita_delete(id_berita, _uid())
        return success(None, "Berita dihapus")


# ================================================================ publik (tanpa login)
@ns.route("/publik")
class Publik(Resource):
    @ns.doc(**PUBLIK)
    @api_doc(ns, publik_out, errors=())
    @measure_execution_time
    def get(self):
        """Akses: publik. Konten website + perangkat desa + potensi dalam satu respons."""
        return success(service.publik_beranda())


@ns.route("/publik/berita")
class PublikBeritaList(Resource):
    @ns.doc(**PUBLIK)
    @api_doc(ns, berita_ringkas_out, many=True, paged=True, errors=(400,))
    @ns.expect(publik_berita_parser)
    @measure_execution_time
    def get(self):
        """Akses: publik. Berita terbit (tanggal_terbit <= hari ini), terbaru dulu. meta: {total, limit, offset}."""
        a = publik_berita_parser.parse_args()
        rows, meta = service.publik_berita_list(a["q"], a["limit"], a["offset"])
        return success(rows, meta=meta)


@ns.route("/publik/berita/<string:slug>")
class PublikBerita(Resource):
    @ns.doc(**PUBLIK)
    @api_doc(ns, berita_out, errors=(404,))
    @measure_execution_time
    def get(self, slug):
        """Akses: publik. Detail berita terbit berdasarkan slug."""
        return success(service.publik_berita(slug))


@ns.route("/publik/file/<path:path>")
class PublikFile(Resource):
    @ns.doc(**PUBLIK)
    @file_doc(ns, errors=(404,))
    def get(self, path):
        """Akses: publik. Gambar website (hanya folder landing/). Cache 30 hari (nama file unik)."""
        return send_file(service.file_publik(path), mimetype="image/jpeg", max_age=30 * 24 * 3600)
