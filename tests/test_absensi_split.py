"""Pemisahan endpoint absensi admin vs aplikasi absen. DB di-mock."""
import unittest
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from api import app
from api.modules.absensi import service
from api.shared.exceptions import ForbiddenError


def token(perms):
    with app.app_context():
        return {"Authorization": "Bearer " + create_access_token(
            identity="5", additional_claims={"id_pegawai": 3, "roles": [], "permissions": perms})}


PEGAWAI = token(["absensi.self", "perizinan.self"])
ADMIN = token(["absensi.view_all", "absensi_gagal.view"])


class RouteAccessTest(unittest.TestCase):
    c = app.test_client()

    def test_pegawai_ditolak_endpoint_admin(self):
        for url in ("/absensi", "/absensi/1", "/absensi/gagal"):
            self.assertEqual(self.c.get(url, headers=PEGAWAI).status_code, 403, url)

    def test_admin_ditolak_endpoint_absen(self):
        self.assertEqual(self.c.get("/absensi/saya/hari-ini", headers=ADMIN).status_code, 403)

    def test_route_lama_tidak_ada(self):
        self.assertIn(self.c.get("/absensi/hari-ini", headers=PEGAWAI).status_code, (404, 405))

    def test_pegawai_hari_ini(self):
        with patch.object(service, "status_hari_ini", return_value={}) as f:
            r = self.c.get("/absensi/saya/hari-ini", headers=PEGAWAI)
        self.assertEqual(r.status_code, 200)
        f.assert_called_once_with(5)


class FotoOwnershipTest(unittest.TestCase):
    def run_foto(self, id_user, ctx_pegawai):
        with patch.object(service, "query") as q, patch.object(service, "_file", return_value="x.jpg"):
            q.get_by_id.return_value = {"id_pegawai": 3, "tanggal": None, "photo_path": "p"}
            q.get_context.return_value = {"id_pegawai": ctx_pegawai}
            return service.foto_path(1, id_user)

    def test_admin_tanpa_cek_pemilik(self):
        self.assertEqual(self.run_foto(None, 99), "x.jpg")

    def test_pemilik_ok(self):
        self.assertEqual(self.run_foto(5, 3), "x.jpg")

    def test_bukan_pemilik_ditolak(self):
        with self.assertRaises(ForbiddenError):
            self.run_foto(5, 99)


if __name__ == "__main__":
    unittest.main()
