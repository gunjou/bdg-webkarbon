# api/modules/auth/endpoint.py
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_restx import Resource

from api.shared.docs import api_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import auth_user_out, login_model, login_out, refresh_model, refresh_out


@ns.route("/login")
class LoginResource(Resource):
    @api_doc(ns, login_out, errors=(400, 401, 403, 422))
    @ns.expect(login_model, validate=True)
    @ns.doc(security=[])
    @measure_execution_time
    def post(self):
        """Akses: publik. Login; field password menerima password atau kode pemulihan."""
        body = request.get_json()
        data = service.login(body["username"].strip(), body["password"])
        return success(data, "Login berhasil")


@ns.route("/refresh")
class RefreshResource(Resource):
    @api_doc(ns, refresh_out, errors=(400, 401, 403))
    @ns.expect(refresh_model, validate=True)
    @ns.doc(security=[])
    @jwt_required(refresh=True, locations=["headers", "json"])  # header Bearer, atau body {"refresh_token"}
    @measure_execution_time
    def post(self):
        """Akses: refresh token. Tukar refresh token dengan access token baru."""
        return success(service.refresh(get_jwt_identity()), "Token diperbarui")


@ns.route("/me")
class MeResource(Resource):
    @api_doc(ns, auth_user_out, errors=(401,))
    @jwt_required()
    @measure_execution_time
    def get(self):
        """Akses: login. Data akun yang sedang login."""
        return success(service.me(get_jwt_identity()))
