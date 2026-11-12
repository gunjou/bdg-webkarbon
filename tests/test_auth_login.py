"""Uji login per client (admin|absensi). DB di-mock: jalankan `venv/bin/python -m unittest tests.test_auth_login`."""
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from api import app
from api.modules.auth import service
from api.shared.exceptions import ForbiddenError

HASH = generate_password_hash("rahasia")
PEGAWAI = {"id_user": 5, "id_pegawai": 3, "username": "budi", "email": None, "password_hash": HASH,
           "kode_pemulihan": "ABC123", "is_active": 1, "pegawai_is_active": 1, "full_name": "Budi",
           "photo_path": "p.jpg", "nip": "123", "jabatan": "Kaur Umum", "face_enrolled": True}
ADMIN_NON_PEGAWAI = {**PEGAWAI, "id_pegawai": None, "pegawai_is_active": None, "full_name": None,
                     "nip": None, "jabatan": None, "face_enrolled": False}
R_PEGAWAI = {"code": "PEGAWAI", "permissions": ["absensi.self", "perizinan.self"]}
R_ADMIN = {"code": "ADMIN", "permissions": ["user.view", "pegawai.manage"]}
R_SUPER = {"code": "SUPER_ADMIN", "permissions": ["*"]}


class LoginClientTest(unittest.TestCase):
    def login(self, user, roles, client):
        with app.app_context(), patch.object(service, "query") as q:
            q.get_user_by_username.return_value = user
            q.get_active_roles.return_value = roles
            self.q = q
            return service.login("budi", "rahasia", client)

    def assert_forbidden(self, user, roles, client):
        with self.assertRaises(ForbiddenError):
            self.login(user, roles, client)
        self.q.insert_login_failure.assert_called_once()
        self.assertEqual(self.q.insert_login_failure.call_args.args[1], "CLIENT_FORBIDDEN")
        self.q.update_last_login.assert_not_called()

    def test_absensi_pegawai_ok(self):
        out = self.login(PEGAWAI, [R_PEGAWAI], "absensi")
        self.assertEqual(out["client"], "absensi")
        self.assertEqual(set(out["user"]), {"id_user", "id_pegawai", "username", "full_name", "nip",
                                            "jabatan", "photo_path", "face_enrolled"})

    def test_admin_ok_returns_roles_permissions(self):
        out = self.login(PEGAWAI, [R_ADMIN, R_PEGAWAI], "admin")
        self.assertEqual(out["user"]["roles"], ["ADMIN", "PEGAWAI"])
        self.assertIn("pegawai.manage", out["user"]["permissions"])

    def test_super_admin_both(self):
        self.login(ADMIN_NON_PEGAWAI, [R_SUPER], "admin")
        self.login(PEGAWAI, [R_SUPER], "absensi")

    def test_pegawai_only_cannot_admin(self):
        self.assert_forbidden(PEGAWAI, [R_PEGAWAI], "admin")

    def test_non_pegawai_cannot_absensi(self):
        self.assert_forbidden(ADMIN_NON_PEGAWAI, [R_ADMIN], "absensi")

    def test_pegawai_without_absensi_permission(self):
        self.assert_forbidden(PEGAWAI, [R_ADMIN], "absensi")


class LoginEndpointTest(unittest.TestCase):
    def post(self, body):
        return app.test_client().post("/auth/login", json=body)

    def test_client_required_and_enum(self):
        self.assertIn(self.post({"username": "a", "password": "b"}).status_code, (400, 422))
        self.assertIn(self.post({"username": "a", "password": "b", "client": "x"}).status_code, (400, 422))

    def test_client_passed_to_service(self):
        with patch.object(service, "login", return_value={}) as login:
            r = self.post({"username": " budi ", "password": "p", "client": "absensi"})
        self.assertEqual(r.status_code, 200)
        login.assert_called_once_with("budi", "p", "absensi")


if __name__ == "__main__":
    unittest.main()
