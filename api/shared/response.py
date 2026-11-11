# api/shared/response.py
from http import HTTPStatus

from api.utils.serializer import serialize_value


def success(data=None, message="Success", status_code=HTTPStatus.OK, meta=None):
    return {
        "code": int(status_code),
        "success": True,
        "message": message,
        "data": serialize_value(data),
        "meta": meta
    }, status_code


def error(message="Terjadi kesalahan", code="GENERAL_ERROR", status_code=HTTPStatus.BAD_REQUEST, errors=None):
    return {
        "success": False,
        "message": message,
        "code": code,
        "errors": errors
    }, status_code
