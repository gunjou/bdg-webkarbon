"""Pemisahan endpoint absensi admin (/absensi) vs aplikasi absen (/presensi). DB di-mock."""
import unittest
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from api import app
from api.modules.presensi import service as presensi
from api.shared.exceptions import NotFoundError


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
        for url in ("/presensi/hari-ini", "/presensi/riwayat"):
            self.assertEqual(self.c.get(url, headers=ADMIN).status_code, 403, url)

    def test_route_lama_tidak_ada(self):
        for url in ("/absensi/hari-ini", "/absensi/saya/hari-ini"):
            self.assertIn(self.c.get(url, headers=PEGAWAI).status_code, (404, 405), url)

    def test_pegawai_hari_ini(self):
        with patch.object(presensi, "hari_ini", return_value={}) as f:
            r = self.c.get("/presensi/hari-ini", headers=PEGAWAI)
        self.assertEqual(r.status_code, 200)
        f.assert_called_once_with(5)


class FotoOwnershipTest(unittest.TestCase):
    """Foto selfie di aplikasi absen hanya milik sendiri; milik orang lain dijawab 404 (id tidak bisa ditebak)."""

    def run_foto(self, pemilik):
        with patch.object(presensi, "_context", return_value={"id_pegawai": 3}), \
             patch.object(presensi.query, "get_by_id", return_value={"id_pegawai": pemilik, "photo_path": "p.jpg"}), \
             patch.object(presensi.storage, "full_path", return_value="/x/p.jpg"), \
             patch.object(presensi.os.path, "exists", return_value=True):
            return presensi.foto_path(5, 1)

    def test_pemilik_ok(self):
        self.assertEqual(self.run_foto(3), "/x/p.jpg")

    def test_bukan_pemilik_404(self):
        with self.assertRaises(NotFoundError):
            self.run_foto(99)


if __name__ == "__main__":
    unittest.main()
