# api/__init__.py
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_restx import Api

from api.core import config
from api.shared.error_handlers import register_jwt_handlers, register_api_handlers

app = Flask(__name__)
CORS(app)


# ==============================
# JWT CONFIG
# ==============================
app.config["JWT_SECRET_KEY"] = config.JWT_SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = config.JWT_ACCESS_TOKEN_EXPIRES
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = config.JWT_REFRESH_TOKEN_EXPIRES
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024  # upload lebih besar -> 413
app.config["ERROR_404_HELP"] = False  # matikan saran URL otomatis flask-restx agar pesan 404 tetap bersih
app.config["PROPAGATE_EXCEPTIONS"] = True  # agar error JWT diteruskan ke handler, bukan ditelan flask-restx

jwt = JWTManager(app)
register_jwt_handlers(jwt)


# ==============================
# FLASK RESTX API
# ==============================
authorizations = {
    "Bearer Auth": {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "description": "Gunakan format: **Bearer &lt;JWT&gt;**"
    }
}

api = Api(
    app,
    version="1.0",
    title="Webkarbon API",
    description="HRIS Backend Webkarbon",
    doc="/docs",
    authorizations=authorizations,
    security="Bearer Auth"
)
register_api_handlers(api)


# ==============================
# MODULES
# ==============================
from api.modules.auth import ns as auth_ns  # noqa: E402
from api.modules.users import ns as users_ns  # noqa: E402
from api.modules.pegawai import ns as pegawai_ns  # noqa: E402
from api.modules.absensi import ns as absensi_ns  # noqa: E402
from api.modules.master import NAMESPACES as master_namespaces  # noqa: E402

api.add_namespace(auth_ns, path="/auth")
api.add_namespace(users_ns, path="/users")
api.add_namespace(pegawai_ns, path="/pegawai")
api.add_namespace(absensi_ns, path="/absensi")
for _ns, _path in master_namespaces:
    api.add_namespace(_ns, path=_path)
