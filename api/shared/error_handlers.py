# api/shared/error_handlers.py
import logging

from flask import request
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt.exceptions import ExpiredSignatureError, PyJWTError
from werkzeug.exceptions import HTTPException

from api.shared.exceptions import AppError
from api.shared.response import error

logger = logging.getLogger(__name__)


def register_jwt_handlers(jwt):
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return error("Token expired", "TOKEN_EXPIRED", 401)

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return error("Token tidak valid", "INVALID_TOKEN", 401)

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return error("Token tidak ditemukan", "TOKEN_MISSING", 401)

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return error("Token telah dicabut", "TOKEN_REVOKED", 401)


def register_api_handlers(api):
    # 404 untuk URL yang tidak terdaftar ditangani Flask, bukan flask-restx
    @api.app.errorhandler(404)
    def handle_not_found(err):
        return error("Endpoint tidak ditemukan", "NOT_FOUND", 404)

    @api.errorhandler(AppError)
    def handle_app_error(err):
        return error(err.message, err.code, err.status_code, err.errors)

    @api.errorhandler(ExpiredSignatureError)
    def handle_expired_signature(err):
        return error("Token expired", "TOKEN_EXPIRED", 401)

    @api.errorhandler(HTTPException)
    def handle_http_error(err):
        # flask-restx menaruh detail validasi di err.data dan memakainya menggantikan body handler
        details = getattr(err, "data", None) or {}
        if details.get("errors"):
            body, status = error("Validasi gagal", "VALIDATION_ERROR", err.code, details["errors"])
        else:
            body, status = error(err.description, err.name.upper().replace(" ", "_"), err.code)
        err.data = body
        return body, status

    @api.errorhandler(Exception)
    def handle_unexpected(err):
        if isinstance(err, (JWTExtendedException, PyJWTError)):
            raise err  # teruskan ke handler JWTManager (401/422), jangan dijadikan 500
        # detail error hanya ke log, jangan bocor ke client
        logger.exception("Unhandled error on %s %s", request.method, request.path)
        return error("Terjadi kesalahan pada server", "INTERNAL_ERROR", 500)
