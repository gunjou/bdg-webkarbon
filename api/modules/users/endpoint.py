# api/modules/users/endpoint.py
from flask import request
from flask_jwt_extended import get_jwt, get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import user_create, user_detail_out, user_out, user_roles_input, user_update


def _actor():
    return int(get_jwt_identity()), set(get_jwt().get("permissions", []))


@ns.route("")
class UserList(Resource):
    @api_doc(ns, user_out, many=True)
    @permission_required("user.view")
    @measure_execution_time
    def get(self):
        """Akses: user.view. Daftar user aktif."""
        return success(service.list_all())

    @api_doc(ns, user_detail_out, status=201, errors=(400, 401, 403, 422))
    @ns.expect(user_create, validate=True)
    @permission_required("user.manage")
    @measure_execution_time
    def post(self):
        """Akses: user.manage. Tambah user + role (kode_pemulihan dibuat otomatis)."""
        data = service.create(request.get_json(), *_actor())
        return success(data, "User berhasil ditambahkan", 201)


@ns.route("/<int:id_user>")
class UserDetail(Resource):
    @api_doc(ns, user_detail_out, errors=(401, 403, 404))
    @permission_required("user.view")
    @measure_execution_time
    def get(self, id_user):
        """Akses: user.view. Detail user (termasuk kode_pemulihan)."""
        return success(service.get(id_user))

    @api_doc(ns, user_detail_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(user_update, validate=True)
    @permission_required("user.manage")
    @measure_execution_time
    def put(self, id_user):
        """Akses: user.manage. Ubah user; password diisi = ganti password."""
        data = service.update(id_user, request.get_json(), *_actor())
        return success(data, "User berhasil diubah")

    @api_doc(ns, errors=(401, 403, 404, 422))
    @permission_required("user.manage")
    @measure_execution_time
    def delete(self, id_user):
        """Akses: user.manage. Nonaktifkan user (soft delete)."""
        service.deactivate(id_user, *_actor())
        return success(None, "User berhasil dinonaktifkan")


@ns.route("/<int:id_user>/activate")
class UserActivate(Resource):
    @api_doc(ns, user_detail_out, errors=(401, 403, 404))
    @permission_required("user.manage")
    @measure_execution_time
    def post(self, id_user):
        """Akses: user.manage. Aktifkan kembali user."""
        return success(service.activate(id_user, *_actor()), "User berhasil diaktifkan")


@ns.route("/<int:id_user>/kode-pemulihan")
class UserKodePemulihan(Resource):
    @api_doc(ns, user_detail_out, errors=(401, 403, 404))
    @permission_required("user.manage")
    @measure_execution_time
    def post(self, id_user):
        """Akses: user.manage. Buat ulang kode_pemulihan."""
        return success(service.reset_kode_pemulihan(id_user, *_actor()), "Kode pemulihan diperbarui")


@ns.route("/<int:id_user>/roles")
class UserRoles(Resource):
    @api_doc(ns, user_detail_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(user_roles_input, validate=True)
    @permission_required("user_role.assign")
    @measure_execution_time
    def put(self, id_user):
        """Akses: user_role.assign. Ganti seluruh role user."""
        data = service.set_roles(id_user, request.get_json()["id_roles"], *_actor())
        return success(data, "Role user berhasil diubah")
