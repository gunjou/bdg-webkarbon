# api/shared/docs.py
"""Dokumentasi respons untuk Swagger/OpenAPI. Hanya dokumentasi: tidak mengubah isi respons.

Pemakaian di endpoint (taruh di atas decorator auth):
    @api_doc(ns, user_out)                      # data = object
    @api_doc(ns, user_out, many=True)           # data = array
    @api_doc(ns, status=201, errors=(401, 403, 422))
"""
from flask_restx import fields

ERROR_DESC = {
    400: "Input tidak valid (format/field wajib)",
    401: "Token tidak ada / tidak valid / expired",
    403: "Tidak punya akses",
    404: "Data tidak ditemukan",
    413: "File terlalu besar",
    422: "Validasi / aturan bisnis gagal (lihat code & errors)",
}
DEFAULT_ERRORS = (401, 403)


def _error_model(ns):
    if "ErrorResponse" not in ns.models:
        ns.model("ErrorResponse", {
            "success": fields.Boolean(example=False),
            "message": fields.String(example="Validasi gagal"),
            "code": fields.String(example="VALIDATION_ERROR", description="Kode error UPPER_SNAKE_CASE"),
            "errors": fields.Raw(description="Detail per field (object) atau null"),
        })
    return ns.models["ErrorResponse"]


def _envelope(ns, model, many, status):
    if model is None:
        name, data = "EmptyResponse", fields.Raw(description="null")
    elif many:
        name, data = f"{model.name}ListResponse", fields.List(fields.Nested(model))
    else:
        name, data = f"{model.name}Response", fields.Nested(model)
    if name not in ns.models:
        ns.model(name, {
            "code": fields.Integer(example=status),
            "success": fields.Boolean(example=True),
            "message": fields.String(example="Success"),
            "data": data,
            "meta": fields.Raw(description="mis. {execution_time_ms}"),
        })
    return ns.models[name]


def api_doc(ns, model=None, *, many=False, status=200, errors=DEFAULT_ERRORS, description="Sukses"):
    def deco(fn):
        for code in errors:
            fn = ns.response(code, ERROR_DESC.get(code, "Gagal"), _error_model(ns))(fn)
        return ns.response(status, description, _envelope(ns, model, many, status))(fn)
    return deco


def file_doc(ns, mimetype="image/jpeg", errors=(401, 403, 404)):
    """Untuk endpoint yang mengembalikan file, bukan JSON."""
    def deco(fn):
        for code in errors:
            fn = ns.response(code, ERROR_DESC.get(code, "Gagal"), _error_model(ns))(fn)
        fn = ns.response(200, f"File {mimetype}")(fn)
        return ns.produces([mimetype])(fn)
    return deco


def audit_fields():
    """Kolom audit standar tabel master."""
    return {
        "is_active": fields.Integer(example=1, description="1 aktif, 0 nonaktif"),
        "created_at": fields.DateTime(),
        "created_by": fields.Integer(),
        "updated_at": fields.DateTime(),
        "updated_by": fields.Integer(),
    }
