import unittest
from unittest.mock import patch

from api.modules.users import service

ROLES = [
    {"id_role": 1, "code": "SUPER_ADMIN", "name": "Super Admin", "permissions": ["*"]},
    {"id_role": 2, "code": "ADMIN", "name": "Admin", "permissions": ["user.manage", "surat.view"]},
    {"id_role": 5, "code": "PEGAWAI", "name": "Pegawai", "permissions": ["absensi.self"]},
]


@patch("api.modules.users.service.query.list_roles", return_value=ROLES)
class ListRolesTest(unittest.TestCase):
    def test_super_admin_lihat_semua(self, _):
        self.assertEqual([r["code"] for r in service.list_roles({"*"})], ["SUPER_ADMIN", "ADMIN", "PEGAWAI"])

    def test_admin_tidak_lihat_role_bintang(self, _):
        self.assertEqual([r["code"] for r in service.list_roles({"user_role.assign"})], ["ADMIN", "PEGAWAI"])

    def test_permissions_tidak_dibocorkan(self, _):
        self.assertEqual(set(service.list_roles({"*"})[0]), {"id_role", "code", "name"})



class UserSchemaTest(unittest.TestCase):
    def test_create_wajib_id_roles(self):
        # dulu id_roles tidak ada di model → service KeyError (500); sekarang divalidasi di request
        from api.modules.users.schema import user_create
        with self.assertRaises(Exception):
            user_create.validate({"username": "budi", "password": "rahasia"})
        user_create.validate({"username": "budi", "password": "rahasia", "id_roles": [2]})

    def test_list_meneruskan_include_inactive(self):
        with patch("api.modules.users.service.query.get_all", return_value=[]) as q:
            service.list_all(1)
        q.assert_called_once_with(1)



@patch("api.modules.users.service.query.get_by_id", return_value={"id_user": 1, "kode_pemulihan": "ABC123"})
class KodePemulihanTest(unittest.TestCase):
    def test_admin_tidak_lihat_kode_super_admin(self, _):
        with patch("api.modules.users.service.query.get_permissions", return_value=["*"]):
            self.assertIsNone(service.get_for(1, {"user.view"})["kode_pemulihan"])

    def test_super_admin_lihat_kode_super_admin(self, _):
        with patch("api.modules.users.service.query.get_permissions", return_value=["*"]):
            self.assertEqual(service.get_for(1, {"*"})["kode_pemulihan"], "ABC123")

    def test_admin_lihat_kode_akun_biasa(self, _):
        with patch("api.modules.users.service.query.get_permissions", return_value=["absensi.self"]):
            self.assertEqual(service.get_for(1, {"user.view"})["kode_pemulihan"], "ABC123")

if __name__ == "__main__":
    unittest.main()
