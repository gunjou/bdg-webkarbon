# api/modules/surat/endpoint.py
from io import BytesIO

from flask import request, send_file
from flask_jwt_extended import get_jwt, get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc, file_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import (agenda_out, agenda_parser, register_out, register_parser, arsip_parser, batal_input, lampiran_parser, perbaiki_input, penandatangan_out, redaksi_input, surat_create, surat_list_out, surat_out,
                     surat_parser, surat_update)

VIEW = ["surat.view", "surat.create"]


def _uid():
    return int(get_jwt_identity())


def _strip(row):
    """Path file tidak dikirim ke client (unduh lewat endpoint /pdf, /arsip, /lampiran)."""
    out = {k: v for k, v in row.items() if k not in ("pdf_path", "arsip_path")}
    out["lampiran"] = [{k: v for k, v in x.items() if k != "path"} for x in row["lampiran"]]
    return out


@ns.route("")
class SuratList(Resource):
    @api_doc(ns, surat_list_out, many=True)
    @ns.expect(surat_parser)
    @permission_required(VIEW)
    @measure_execution_time
    def get(self):
        """Akses: surat.view / surat.create. Daftar surat terbaru, filter status/jenis/tahun/q, maks 200."""
        return success(service.search(surat_parser.parse_args()))

    @api_doc(ns, surat_out, status=201, errors=(400, 401, 403, 404, 422))
    @ns.expect(surat_create, validate=True)
    @permission_required("surat.create")
    @measure_execution_time
    def post(self):
        """Akses: surat.create. Buat draft (salin skema & redaksi jenis surat aktif)."""
        return success(_strip(service.create(request.get_json(), _uid())), "Draft surat berhasil dibuat", 201)


@ns.route("/agenda")
class SuratAgenda(Resource):
    @api_doc(ns, agenda_out, errors=(401, 403, 422))
    @ns.expect(agenda_parser)
    @permission_required(VIEW)
    @measure_execution_time
    def get(self):
        """Akses: surat.view / surat.create. Buku Agenda Surat Keluar setahun (surat bernomor, termasuk batal)."""
        return success(service.agenda(agenda_parser.parse_args().get("tahun")))


@ns.route("/register")
class SuratRegister(Resource):
    @api_doc(ns, register_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(register_parser)
    @permission_required(VIEW)
    @measure_execution_time
    def get(self):
        """Akses: surat.view / surat.create. Buku Register per jenis surat setahun + kolom field register."""
        args = register_parser.parse_args()
        return success(service.register(args["id_jenis_surat"], args.get("tahun")))


@ns.route("/penandatangan")
class SuratPenandatangan(Resource):
    @api_doc(ns, penandatangan_out, many=True)
    @permission_required(VIEW)
    @measure_execution_time
    def get(self):
        """Akses: surat.view / surat.create. Pilihan penandatangan (pegawai aktif, jabatan can_sign = 1)."""
        return success(service.list_penandatangan())


@ns.route("/<int:id_surat>")
class SuratDetail(Resource):
    @api_doc(ns, surat_out, errors=(401, 403, 404))
    @permission_required(VIEW)
    @measure_execution_time
    def get(self, id_surat):
        """Akses: surat.view / surat.create. Detail surat."""
        return success(_strip(service.get(id_surat)))

    @api_doc(ns, surat_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(surat_update, validate=True)
    @permission_required("surat.create")
    @measure_execution_time
    def put(self, id_surat):
        """Akses: surat.create. Simpan isian & penandatangan draft (format dicek; kelengkapan dicek saat terbit)."""
        return success(_strip(service.update(id_surat, request.get_json(), _uid())), "Draft surat berhasil disimpan")


@ns.route("/<int:id_surat>/redaksi")
class SuratRedaksi(Resource):
    @api_doc(ns, surat_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(redaksi_input, validate=True)
    @permission_required("surat.edit_redaksi")
    @measure_execution_time
    def put(self, id_surat):
        """Akses: surat.edit_redaksi. Sesuaikan redaksi surat ini saja (draft)."""
        data = service.set_redaksi(id_surat, request.get_json().get("redaksi"), _uid())
        return success(_strip(data), "Redaksi surat berhasil disimpan")

    @api_doc(ns, surat_out, errors=(401, 403, 404, 422))
    @permission_required("surat.edit_redaksi")
    @measure_execution_time
    def delete(self, id_surat):
        """Akses: surat.edit_redaksi. Kembalikan ke template standar jenis surat (draft)."""
        return success(_strip(service.reset_redaksi(id_surat, _uid())), "Redaksi dikembalikan ke template standar")


@ns.route("/<int:id_surat>/lampiran")
class SuratLampiranList(Resource):
    @api_doc(ns, surat_out, status=201, errors=(400, 401, 403, 404, 413, 422))
    @ns.expect(lampiran_parser)
    @permission_required("surat.create")
    @measure_execution_time
    def post(self, id_surat):
        """Akses: surat.create. Upload lampiran (PDF/JPG/PNG). multipart/form-data."""
        args = lampiran_parser.parse_args()
        data = service.add_lampiran(id_surat, args["nama"], args["file"].read(), _uid())
        return success(_strip(data), "Lampiran berhasil ditambahkan", 201)


@ns.route("/<int:id_surat>/lampiran/<string:id_lampiran>")
class SuratLampiranDetail(Resource):
    @file_doc(ns, mimetype="application/pdf")
    @permission_required(VIEW)
    def get(self, id_surat, id_lampiran):
        """Akses: surat.view / surat.create. Unduh lampiran (pdf/jpg/png)."""
        path, mimetype, nama = service.get_lampiran_file(id_surat, id_lampiran)
        return send_file(path, mimetype=mimetype, download_name=f"{nama}{path[path.rfind('.'):]}")

    @api_doc(ns, surat_out, errors=(401, 403, 404, 422))
    @permission_required("surat.create")
    @measure_execution_time
    def delete(self, id_surat, id_lampiran):
        """Akses: surat.create. Hapus lampiran."""
        return success(_strip(service.delete_lampiran(id_surat, id_lampiran, _uid())), "Lampiran berhasil dihapus")


@ns.route("/<int:id_surat>/preview")
class SuratPreview(Resource):
    @file_doc(ns, mimetype="application/pdf", errors=(401, 403, 404, 422))
    @permission_required(VIEW)
    def get(self, id_surat):
        """Akses: surat.view / surat.create. Preview PDF (draft: watermark DRAF, belum bernomor)."""
        return send_file(BytesIO(service.preview(id_surat)), mimetype="application/pdf", download_name="preview.pdf")


@ns.route("/<int:id_surat>/pdf")
class SuratPdf(Resource):
    @file_doc(ns, mimetype="application/pdf", errors=(401, 403, 404, 422))
    @permission_required(VIEW)
    def get(self, id_surat):
        """Akses: surat.view / surat.create. PDF surat: diterbitkan = PDF tersimpan (untuk dicetak);
        draft = watermark DRAF; dibatalkan = watermark DIBATALKAN."""
        pdf, nama = service.get_pdf(id_surat)
        return send_file(BytesIO(pdf), mimetype="application/pdf", download_name=nama)


@ns.route("/<int:id_surat>/terbitkan")
class SuratTerbitkan(Resource):
    @api_doc(ns, surat_out, errors=(401, 403, 404, 422))
    @permission_required("surat.terbitkan")
    @measure_execution_time
    def post(self, id_surat):
        """Akses: surat.terbitkan. Terbitkan nomor (isian lengkap & penandatangan wajib); tanggal surat = hari ini."""
        return success(_strip(service.terbitkan(id_surat, _uid())), "Surat berhasil diterbitkan")


@ns.route("/<int:id_surat>/perbaiki")
class SuratPerbaiki(Resource):
    @api_doc(ns, surat_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(perbaiki_input, validate=True)
    @permission_required("surat.terbitkan")
    @measure_execution_time
    def post(self, id_surat):
        """Akses: surat.terbitkan (+ surat.edit_redaksi bila redaksi diubah). Perbaikan & cetak ulang dengan
        nomor yang sama, selama scan arsip belum di-upload."""
        perms = set(get_jwt().get("permissions", []))
        boleh = bool(perms & {"*", "surat.edit_redaksi"})
        return success(_strip(service.perbaiki(id_surat, request.get_json(), boleh, _uid())), "Surat berhasil diperbaiki")


@ns.route("/<int:id_surat>/arsip")
class SuratArsip(Resource):
    @file_doc(ns, mimetype="application/pdf")
    @permission_required(VIEW)
    def get(self, id_surat):
        """Akses: surat.view / surat.create. Unduh scan arsip."""
        path, mimetype, nama = service.get_arsip_file(id_surat)
        return send_file(path, mimetype=mimetype, download_name=nama)

    @api_doc(ns, surat_out, errors=(400, 401, 403, 404, 413, 422))
    @ns.expect(arsip_parser)
    @permission_required("surat.terbitkan")
    @measure_execution_time
    def post(self, id_surat):
        """Akses: surat.terbitkan. Upload scan surat bertanda tangan & berstempel; surat terkunci dari perbaikan."""
        data = service.arsipkan(id_surat, arsip_parser.parse_args()["file"].read(), _uid())
        return success(_strip(data), "Scan arsip berhasil disimpan")


@ns.route("/<int:id_surat>/batal")
class SuratBatal(Resource):
    @api_doc(ns, surat_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(batal_input, validate=True)
    @permission_required("surat.cancel")
    @measure_execution_time
    def post(self, id_surat):
        """Akses: surat.cancel. Batalkan surat (alasan wajib). Nomor yang sudah terbit tetap melekat & hangus."""
        return success(_strip(service.batalkan(id_surat, request.get_json().get("alasan"), _uid())),
                       "Surat berhasil dibatalkan")


@ns.route("/<int:id_surat>/pengganti")
class SuratPengganti(Resource):
    @api_doc(ns, surat_out, status=201, errors=(401, 403, 404, 422))
    @permission_required("surat.create")
    @measure_execution_time
    def post(self, id_surat):
        """Akses: surat.create. Buat draft pengganti dari surat bernomor yang dibatalkan (isian disalin)."""
        return success(_strip(service.buat_pengganti(id_surat, _uid())), "Draft surat pengganti berhasil dibuat", 201)
