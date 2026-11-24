-- =====================================================================
-- 018: jenis surat SP (Surat Pengantar), layout "pengantar":
--   Kepada Yth. di kanan atas, judul + NOMOR di tengah, tabel No | Uraian | Banyaknya | Keterangan.
--   Kode klasifikasi 315 (lanjutan 301-314); dilewati bila code SP / klasifikasi 315 sudah dipakai.
-- Aman dijalankan ulang.
-- =====================================================================
BEGIN;

INSERT INTO jenis_surat (code, name, kode_klasifikasi, skema_form, template_isi, persyaratan, versi, sort_order, created_at)
SELECT 'SP', 'Surat Pengantar', '315', '{"layout": "pengantar", "sections": [{"key": "tujuan", "label": "Tujuan Surat", "type": "fields", "fields": [{"key": "kepada", "label": "Kepada Yth.", "type": "text", "required": true, "register": true}, {"key": "di_tempat", "label": "Di (tempat tujuan)", "type": "text"}]}, {"key": "dokumen", "label": "Dokumen yang Dikirim", "type": "daftar", "columns": [{"key": "uraian", "label": "Uraian", "type": "text", "required": true}, {"key": "banyaknya", "label": "Banyaknya", "type": "text", "required": true}, {"key": "keterangan", "label": "Keterangan", "type": "text"}]}]}'::jsonb, '{{ tabel(dokumen) }}', '[]'::jsonb, 1, 26, now()
WHERE NOT EXISTS (SELECT 1 FROM jenis_surat WHERE code = 'SP' OR kode_klasifikasi = '315');

COMMIT;
