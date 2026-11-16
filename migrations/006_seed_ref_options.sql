-- =====================================================================
-- 006: opsi bawaan ref_options (is_system = 1: kode tetap, tidak bisa dinonaktifkan)
--   PEKERJAAN & DUSUN tidak di-seed: diisi admin desa dari menu master.
-- Aman dijalankan ulang (ON CONFLICT DO NOTHING).
-- =====================================================================
BEGIN;

INSERT INTO ref_options (group_code, code, label, sort_order, is_system, created_at) VALUES
('AGAMA', 'ISLAM',     'Islam',     1, 1, now()),
('AGAMA', 'KRISTEN',   'Kristen',   2, 1, now()),
('AGAMA', 'KATOLIK',   'Katolik',   3, 1, now()),
('AGAMA', 'HINDU',     'Hindu',     4, 1, now()),
('AGAMA', 'BUDDHA',    'Buddha',    5, 1, now()),
('AGAMA', 'KONGHUCU',  'Konghucu',  6, 1, now()),

('STATUS_PERKAWINAN', 'BELUM_KAWIN', 'Belum Kawin', 1, 1, now()),
('STATUS_PERKAWINAN', 'KAWIN',       'Kawin',       2, 1, now()),
('STATUS_PERKAWINAN', 'CERAI_HIDUP', 'Cerai Hidup', 3, 1, now()),
('STATUS_PERKAWINAN', 'CERAI_MATI',  'Cerai Mati',  4, 1, now()),

('KEWARGANEGARAAN', 'WNI', 'WNI', 1, 1, now()),
('KEWARGANEGARAAN', 'WNA', 'WNA', 2, 1, now()),

('PENDIDIKAN', 'TIDAK_SEKOLAH', 'Tidak/Belum Sekolah',  1, 1, now()),
('PENDIDIKAN', 'BELUM_TAMAT_SD','Belum Tamat SD/Sederajat', 2, 1, now()),
('PENDIDIKAN', 'SD',            'Tamat SD/Sederajat',   3, 1, now()),
('PENDIDIKAN', 'SLTP',          'SLTP/Sederajat',       4, 1, now()),
('PENDIDIKAN', 'SLTA',          'SLTA/Sederajat',       5, 1, now()),
('PENDIDIKAN', 'D1_D2',         'Diploma I/II',         6, 1, now()),
('PENDIDIKAN', 'D3',            'Akademi/Diploma III/Sarjana Muda', 7, 1, now()),
('PENDIDIKAN', 'S1',            'Diploma IV/Strata I',  8, 1, now()),
('PENDIDIKAN', 'S2',            'Strata II',            9, 1, now()),
('PENDIDIKAN', 'S3',            'Strata III',          10, 1, now()),

('HUBUNGAN_KELUARGA', 'KEPALA_KELUARGA', 'Kepala Keluarga', 1, 1, now()),
('HUBUNGAN_KELUARGA', 'SUAMI',           'Suami',           2, 1, now()),
('HUBUNGAN_KELUARGA', 'ISTRI',           'Istri',           3, 1, now()),
('HUBUNGAN_KELUARGA', 'ANAK',            'Anak',            4, 1, now()),
('HUBUNGAN_KELUARGA', 'MENANTU',         'Menantu',         5, 1, now()),
('HUBUNGAN_KELUARGA', 'CUCU',            'Cucu',            6, 1, now()),
('HUBUNGAN_KELUARGA', 'ORANG_TUA',       'Orang Tua',       7, 1, now()),
('HUBUNGAN_KELUARGA', 'MERTUA',          'Mertua',          8, 1, now()),
('HUBUNGAN_KELUARGA', 'FAMILI_LAIN',     'Famili Lain',     9, 1, now()),
('HUBUNGAN_KELUARGA', 'PEMBANTU',        'Pembantu',       10, 1, now()),
('HUBUNGAN_KELUARGA', 'LAINNYA',         'Lainnya',        11, 1, now())
ON CONFLICT (group_code, code) DO NOTHING;

COMMIT;
