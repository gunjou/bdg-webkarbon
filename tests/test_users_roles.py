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


if __name__ == "__main__":
    unittest.main()
