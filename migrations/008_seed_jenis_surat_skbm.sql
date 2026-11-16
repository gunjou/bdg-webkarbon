-- =====================================================================
-- 008: seed jenis surat SKBM (Surat Keterangan Belum Menikah) dari contoh surat asli desa
--   + label kewarganegaraan WNI -> "Indonesia" (sesuai cetakan surat desa; kode tetap WNI).
--   Redaksi & persyaratan bisa diubah admin dari menu Jenis Surat.
-- Aman dijalankan ulang (ON CONFLICT DO NOTHING; label hanya diubah bila masih bawaan).
-- =====================================================================
BEGIN;

INSERT INTO jenis_surat (code, name, kode_klasifikasi, skema_form, template_isi, persyaratan, versi, sort_order, created_at)
VALUES (
    'SKBM',
    'Surat Keterangan Belum Menikah',
    '148.1',
    '{"sections": [{"key": "pemohon", "label": "Data Pemohon", "type": "penduduk", "tampilkan": ["nama", "ttl", "jenis_kelamin", "agama", "status_perkawinan", "pekerjaan", "kewarganegaraan", "alamat"]}, {"key": "lainnya", "label": "Keperluan", "type": "fields", "fields": [{"key": "keperluan", "label": "Keperluan (salah satu syarat ...)", "type": "text", "required": true, "register": true}]}]}'::jsonb,
    '<p>Yang bertandatangan dibawah ini Kepala Desa {{ desa.nama }}, Kecamatan {{ desa.kecamatan }}, Kabupaten {{ desa.kabupaten }}, menerangkan dengan sebenarnya bahwa:</p>{{ biodata(pemohon) }}<p>Adalah penduduk Desa {{ desa.nama }} Kecamatan {{ desa.kecamatan }} Kabupaten {{ desa.kabupaten }}, sejauh pengamatan dan penelitian yang kami lakukan, memang benar yang bersangkutan belum pernah sama sekali melangsungkan pernikahan sampai dengan saat ini.</p><p>Surat Keterangan ini diberikan kepada yang bersangkutan sebagai salah satu syarat {{ keperluan }}.</p><p>Demikian Surat Keterangan ini kami buat dengan sebenarnya untuk dapat dipergunakan sebagaimana mestinya.</p>',
    '[{"nama": "KTP", "wajib": 1}, {"nama": "Kartu Keluarga", "wajib": 1}]'::jsonb,
    1, 1, now()
)
ON CONFLICT (code) DO NOTHING;

UPDATE ref_options SET label = 'Indonesia', updated_at = now()
WHERE group_code = 'KEWARGANEGARAAN' AND code = 'WNI' AND label = 'WNI';

COMMIT;
