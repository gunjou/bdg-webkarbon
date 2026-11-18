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


if __name__ == "__main__":
    unittest.main()
