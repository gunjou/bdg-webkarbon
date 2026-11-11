-- =====================================================================
-- 002: kode_pemulihan + role default
-- Aman dijalankan ulang (IF NOT EXISTS / ON CONFLICT).
-- =====================================================================
BEGIN;

INSERT INTO roles (code, name, permissions, is_system) VALUES
('SUPER_ADMIN', 'Super Admin', '["*"]', 1),
('ADMIN', 'Admin', '[
    "user.view", "user.manage", "user_role.assign",
    "login_failure.view",
    "pegawai.view", "pegawai.manage", "pegawai.enroll_face",
    "jabatan.manage", "lokasi_kantor.manage", "jadwal_kerja.manage",
    "hari_libur.manage", "jenis_izin.manage",
    "absensi.view_all", "absensi_gagal.view",
    "perizinan.view_all"
]', 1),
('SEKDES', 'Sekretaris Desa', '[
    "pegawai.view", "absensi.view_all", "perizinan.view_all", "perizinan.review"
]', 1),
('KADES', 'Kepala Desa', '[
    "pegawai.view", "absensi.view_all", "perizinan.view_all", "perizinan.review"
]', 1),
('PEGAWAI', 'Pegawai', '["absensi.self", "perizinan.self"]', 1)
ON CONFLICT (code) DO NOTHING;

COMMIT;
