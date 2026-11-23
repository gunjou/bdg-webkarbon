# SCHEMA

Ringkasan dari `migrations/001_init.sql` s/d `009_can_sign_dan_judul_surat.sql`. PostgreSQL 13+.
Semua kolom waktu `TIMESTAMPTZ`. Flag = `SMALLINT` 0/1. Hampir semua tabel master punya
`is_active, created_at, created_by, updated_at, updated_by` (ditulis "+ audit" di bawah).

## 1. Login

### users — akun login

| Kolom          | Tipe                       | Catatan                            |
| -------------- | -------------------------- | ---------------------------------- |
| id_user        | INTEGER PK                 |                                    |
| id_pegawai     | INTEGER FK pegawai, UNIQUE | NULL = akun non-pegawai            |
| username       | VARCHAR(50)                | unik case-insensitive              |
| email          | VARCHAR(150)               | unik case-insensitive, boleh NULL  |
| password_hash  | VARCHAR(255)               | werkzeug hash                      |
| kode_pemulihan | VARCHAR(12)                | plain, 6 karakter acak, boleh NULL |
| last_login_at  | TIMESTAMPTZ                |                                    |
| + audit        |                            |                                    |

### roles — paket hak akses

| Kolom       | Tipe               | Catatan                                  |
| ----------- | ------------------ | ---------------------------------------- |
| id_role     | INTEGER PK         |                                          |
| code        | VARCHAR(50) UNIQUE | lihat daftar role di bawah               |
| name        | VARCHAR(100)       |                                          |
| permissions | JSONB array        | mis. `["absensi.self"]`, `["*"]` = semua |
| is_system   | SMALLINT           | 1 = role bawaan                          |
| + audit     |                    |                                          |

### user_roles — user ↔ role (banyak-ke-banyak)

`id_user_role` PK, `id_user` FK (CASCADE), `id_role` FK, `created_at`, `created_by`. UNIQUE (id_user, id_role).
Cabut role = DELETE baris.

### login_failures — gagal login (hanya username terdaftar)

`id_login_failure` BIGINT PK, `id_user` FK (CASCADE), `error_code`, `error_message`, `created_at`.
error_code: `WRONG_PASSWORD, USER_INACTIVE, PEGAWAI_INACTIVE, NO_ACTIVE_ROLE, CLIENT_FORBIDDEN, SERVER_ERROR`.

### settings — parameter sistem

`id_setting` PK, `key` VARCHAR(100) UNIQUE, `value` JSONB, `description`, + audit (tanpa is_active).
Daftar key valid ada di kode; key yang belum punya baris memakai default dari kode.

| Key | Default | Dikelola di |
|---|---|---|
| `ABSEN_MASUK_BUKA_MENIT`, `GPS_MAX_AKURASI_METER`, `FACE_MATCH_THRESHOLD` | 60, 50, 0.5 | `presensi/service.py` (belum ada UI) |
| `desa.nama`, `desa.kecamatan`, `desa.kabupaten` | Karang Bongkot, Labuapi, Lombok Barat | `PUT /settings` |
| `desa.alamat`, `desa.email`, `desa.website` | dari kop surat asli desa | `PUT /settings` |
| `desa.logo_path` | logo kanan kop; `null` = logo desa bawaan (`api/assets/logo-desa.png`) | `POST /settings/logo` |
| `desa.logo_kiri_path` | logo kiri kop; `null` = logo Kabupaten Lombok Barat bawaan (`api/assets/logo-kabupaten.svg`) | `POST /settings/logo?posisi=kiri` |
| `surat.kode_desa` | `KRB` | `PUT /settings` |
| `surat.format_nomor` | `{klasifikasi}/{urut}/{kode_desa}/{tahun}` (wajib memuat `{urut}`) | `PUT /settings` |
| `surat.cakupan_nomor` | `GLOBAL` (`GLOBAL` / `PER_JENIS`) | `PUT /settings` |
| `surat.ukuran_kertas` | `F4` (`F4` 215×330 mm / `A4`) | `PUT /settings` |

Registry key desa & surat: `REGISTRY` di `api/modules/settings/service.py`.

## 2. Master kepegawaian & absensi

| Tabel         | Kolom utama                                                                                                | Catatan                                                           |
| ------------- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| jabatan       | id_jabatan, name, sort_order, can_sign (migrasi 004), + audit                                              | name unik case-insensitive; `can_sign = 1` = boleh tanda tangan surat (awal: Kepala Desa & Sekretaris Desa, migrasi 009) |
| lokasi_kantor | id_lokasi_kantor, name, latitude NUMERIC(9,6), longitude NUMERIC(9,6), radius_meter (default 100), + audit | titik & radius absen sah                                          |
| jadwal_kerja  | id_jadwal_kerja, name, jadwal_harian JSONB, toleransi_terlambat_menit, + audit                             | lihat contoh JSON di bawah                                        |
| hari_libur    | id_hari_libur, tanggal DATE, name, jenis, + audit                                                          | jenis: `nasional, cuti_bersama, lokal`; 1 libur aktif per tanggal |
| jenis_izin    | id_jenis_izin, code UNIQUE, name, butuh_lampiran, dihitung_hadir, + audit                                  | sakit, izin, cuti, dinas luar, ...                                |

`jadwal_harian` (hari libur = null):

```json
{
  "senin": { "masuk": "07:30", "pulang": "15:30" },
  "jumat": { "masuk": "07:30", "pulang": "11:30" },
  "sabtu": null,
  "minggu": null
}
```

### pegawai

| Kolom            | Tipe             | Catatan                                             |
| ---------------- | ---------------- | --------------------------------------------------- |
| id_pegawai       | INTEGER PK       |                                                     |
| id_jabatan       | FK jabatan       | wajib                                               |
| id_jadwal_kerja  | FK jadwal_kerja  |                                                     |
| nip              | VARCHAR(30)      | unik jika diisi                                     |
| full_name        | VARCHAR(150)     |                                                     |
| phone            | VARCHAR(20)      |                                                     |
| photo_path       | VARCHAR(255)     | foto enrollment                                     |
| embedding        | REAL[]           | NULL = belum enrollment wajah (`FACE_NOT_ENROLLED`) |
| + audit          |                  |                                                     |

## 3. Transaksi absensi

### absensi — absen BERHASIL (+ hasil koreksi, migrasi 003)

`id_absensi` BIGINT PK, `id_pegawai` FK, `id_lokasi_kantor` FK, `tanggal` DATE, `jenis` (`masuk|pulang`),
`waktu_absen` TIMESTAMPTZ, `latitude`, `longitude`, `akurasi_gps`, `jarak_meter`, `skor_wajah`,
`photo_path` (wajib), `jam_jadwal` TIME (snapshot), `terlambat_menit` (snapshot, ≥0),
`status` (`tepat_waktu|terlambat|pulang_cepat`), `created_at`, `created_by`, `updated_at`, `updated_by`.
`id_lokasi_kantor`, `latitude`, `longitude`, `photo_path` NULL untuk absen hasil koreksi.
UNIQUE (id_pegawai, tanggal, jenis) → 1x masuk & 1x pulang per hari.

### absensi_gagal — semua percobaan gagal (client & server)

`id_absensi_gagal` BIGINT PK, `id_pegawai` FK, `id_lokasi_kantor` FK?, `jenis` (`masuk|pulang`|NULL),
`source` (`client|server`), `stage` (`GPS, CAMERA, LOCATION, FACE, SCHEDULE, SYSTEM`),
`error_code` (mis. `GPS_PERMISSION_DENIED, OUTSIDE_RADIUS, FACE_NOT_MATCH, OUTSIDE_TIME_WINDOW`),
`error_message`, `latitude`, `longitude`, `akurasi_gps`, `jarak_meter`, `skor_wajah`,
`photo_path` (hanya stage FACE), `detail` JSONB, `created_at`.

### perizinan — pengajuan izin & koreksi absen

`id_perizinan` PK, `id_pegawai` FK, `id_jenis_izin` FK?, `jenis_pengajuan` (`koreksi|izin`),
`jenis_absen` (`masuk|pulang`)?, `tanggal_mulai`, `tanggal_selesai`, `jam_koreksi` TIME?, `alasan`,
`lampiran_path`, `status` (`diajukan` default, `disetujui, ditolak, dibatalkan`),
`reviewed_by` FK users, `reviewed_at`, `catatan_peninjau`, `created_at, created_by, updated_at, updated_by`.

Aturan (CHECK):

- `tanggal_selesai >= tanggal_mulai`
- `izin` → wajib `id_jenis_izin`; `jenis_absen` & `jam_koreksi` NULL
- `koreksi` → `id_jenis_izin` NULL; wajib `jenis_absen` & `jam_koreksi`; hanya 1 tanggal
- status `disetujui|ditolak` → wajib `reviewed_by` & `reviewed_at`

## 4. Persuratan (migrasi 004–009)

Alur: draft → diterbitkan (dapat nomor) → [perbaikan selama belum diarsip] → diarsip (scan ditandatangani, terkunci).
Draft / diterbitkan → dibatalkan (alasan wajib; nomor yang sudah terbit tetap melekat & hangus).
Pengesahan tetap manual (tanda tangan basah + stempel). Ketentuan lengkap: docstring
`api/modules/surat/service.py` dan `api/modules/jenis_surat/service.py`.

### ref_options — daftar pilihan sederhana

`id_ref_option` PK, `group_code`, `code`, `label`, `sort_order`, `is_system`, + audit. UNIQUE (group_code, code).
Tabel lain menyimpan **code**, bukan id. `is_system = 1` (seed 006) = kode & grup tetap, tidak bisa dinonaktifkan.
Grup bawaan: `AGAMA, STATUS_PERKAWINAN, KEWARGANEGARAAN, PENDIDIKAN, HUBUNGAN_KELUARGA` (seed 006);
`PEKERJAAN, DUSUN` diisi admin desa. Label `WNI` = "Indonesia" (seed 008, sesuai cetakan surat desa).

### penduduk — data induk warga (sumber pencarian pemohon)

| Kolom | Tipe | Catatan |
|---|---|---|
| id_penduduk | INTEGER PK | |
| nik, no_kk | VARCHAR(16) | 16 digit; NIK unik jika diisi (termasuk nonaktif) |
| full_name | VARCHAR(150) | wajib; index `lower(full_name)` untuk cari awalan |
| tempat_lahir, tanggal_lahir | VARCHAR(100), DATE | |
| jenis_kelamin | CHAR(1) | `L` / `P` |
| agama, pekerjaan, status_perkawinan, kewarganegaraan, dusun | VARCHAR(50) | code ref_options; kewarganegaraan default `WNI` |
| rt, rw | VARCHAR(3) | disimpan 3 digit (`002`) |
| alamat | VARCHAR(255) | detail opsional |
| + audit | | `is_active = 0` = pindah / meninggal |

Hanya diisi dari menu Penduduk. Pemohon surat yang diisi manual **tidak** masuk ke sini.

### jenis_surat — cetakan surat

| Kolom | Tipe | Catatan |
|---|---|---|
| id_jenis_surat | INTEGER PK | |
| code | VARCHAR(30) UNIQUE | mis. `SKBM`; terkunci bila sudah ada surat (dipakai cakupan nomor `PER_JENIS`) |
| name | VARCHAR(150) | judul surat |
| kode_klasifikasi | VARCHAR(30) | mis. `148.1` |
| skema_form | JSONB object | form dinamis, lihat di bawah |
| template_isi | TEXT | HTML + placeholder `{{ ... }}` (redaksi dari pembuka s/d penutup) |
| persyaratan | JSONB array | `[{"nama": "KTP", "wajib": 1}]` |
| versi | INTEGER | naik 1 setiap skema_form / template_isi berubah |
| sort_order, + audit | | |

Seed 008: `SKBM` (Surat Keterangan Belum Menikah, 148.1) dari contoh surat asli desa.

`skema_form.layout` — `keterangan` (default) | `dinas` (surat biasa/undangan; field `sifat, lampiran, perihal, kepada,
di_tempat, tembusan` dicetak di kepala surat; section penduduk opsional). Detail: docstring `jenis_surat/render.py`.

`skema_form` — 4 tipe section; key section & field unik di seluruh skema (huruf kecil/angka/`_`):

```json
{"sections": [
  {"key": "pemohon", "label": "Data Pemohon", "type": "penduduk",
   "tampilkan": ["nama", "ttl", "jenis_kelamin", "agama", "status_perkawinan", "pekerjaan", "kewarganegaraan", "alamat"]},
  {"key": "lainnya", "label": "Keperluan", "type": "fields",
   "fields": [{"key": "keperluan", "label": "Keperluan", "type": "text", "required": true, "register": true}]},
  {"key": "batas", "label": "Batas Tanah", "type": "daftar",
   "columns": [{"key": "arah", "label": "Arah", "type": "text", "required": true}]},
  {"key": "uraian", "label": "Uraian", "type": "teks_bebas", "required": true}
]}
```

- `penduduk`: biodata 1 orang; `tampilkan` ⊂ `nama, nik, no_kk, ttl, jenis_kelamin, agama, status_perkawinan,
  pekerjaan, kewarganegaraan, alamat`. **Section penduduk pertama = pemohon utama** (wajib ada minimal satu).
- `fields`: type `text | textarea | number | date | rupiah | select`; `select` butuh `options_group` (grup
  ref_options) atau `options` (daftar tetap). `register: true` = jadi kolom di buku register.
- `daftar`: tabel isian berulang (`columns`, type sama dengan fields kecuali textarea).
- `teks_bebas`: paragraf HTML yang ditulis operator.

`template_isi`: HTML dibersihkan (tag `p b strong i em u br table tbody tr td th ul ol li span`, style hanya
perataan/tebal/miring/garis/lebar/indentasi), hanya `{{ ... }}` (tanpa `{% %}` / `{# #}`), dirender di Jinja
**sandbox**. Nama yang boleh dipakai: `desa.nama|kecamatan|kabupaten|alamat`, key field, key section, dan helper
`biodata(orang)`, `tabel(daftar)`, `tgl_indo(tanggal)`, `terbilang(angka, "rupiah")`, `label(kode)`.

### nomor_urut_surat — counter nomor

`id_nomor_urut_surat` PK, `cakupan` (`GLOBAL` atau code jenis surat), `tahun`, `nomor_terakhir`, `updated_at`.
UNIQUE (cakupan, tahun). Hanya maju (`INSERT ... ON CONFLICT DO UPDATE ... + 1`), reset per tahun, ikut rollback
bila penerbitan gagal. Nomor surat yang dibatalkan tetap hangus.

### surat — satu baris = satu surat keluar

| Kolom | Catatan |
|---|---|
| id_surat, id_jenis_surat | |
| judul | salinan `jenis_surat.name` saat draft dibuat (migrasi 009) |
| id_penduduk | opsional; NULL = pemohon diisi manual |
| nama_pemohon, nik_pemohon | pemohon utama (section penduduk pertama); untuk daftar & pencarian |
| id_surat_diganti | surat lama yang digantikan surat ini |
| status | `draft` → `diterbitkan` / `dibatalkan` |
| nomor_surat (UNIQUE), nomor_urut, tanggal_surat | NULL saat draft; tanggal = hari terbit (WITA) |
| versi_template, skema_form, redaksi | **salinan** dari jenis surat saat draft dibuat; render selalu memakai salinan ini |
| redaksi_diubah | 1 = redaksi disesuaikan khusus surat ini |
| data | isian + snapshot biodata semua pihak (bentuk di bawah) |
| lampiran | `[{"id", "nama", "path", "mimetype"}]` (pdf/jpg/png) |
| id_penandatangan, atas_nama | pegawai (jabatan `can_sign = 1`); `atas_nama = 1` bila bukan Kepala Desa → dicetak "a.n. Kepala Desa ..." |
| data_penandatangan | snapshot `{id_pegawai, nama, jabatan, nip, atas_nama}` saat terbit/perbaikan |
| diterbitkan_oleh, diterbitkan_pada | |
| pdf_path | PDF hasil sistem (`uploads/surat/pdf/`) |
| arsip_path | scan bertanda tangan & berstempel (`uploads/surat/arsip/`); terisi = surat terkunci |
| alasan_batal | wajib bila dibatalkan |
| riwayat | `[{"aksi", "oleh", "pada", "catatan"}]`; aksi: `dibuat, redaksi_diubah, redaksi_dikembalikan, lampiran_ditambah, lampiran_dihapus, diterbitkan, diperbaiki, diarsipkan, dibatalkan, diganti` |
| + created_*, updated_* | tanpa is_active (siklus diatur status) |

CHECK: draft tanpa nomor/penerbit; diterbitkan wajib lengkap (nomor, nomor_urut, tanggal, penandatangan,
data_penandatangan, penerbit); dibatalkan wajib `alasan_batal`; `arsip_path` hanya bila bernomor;
`id_surat_diganti <> id_surat`.

Bentuk `surat.data`:

```json
{
  "pemohon": {"id_penduduk": 12, "nama": "GUGUN JOFANDI", "nik": "5201...", "no_kk": null,
              "tempat_lahir": "Perampuan", "tanggal_lahir": "1998-11-03", "jenis_kelamin": "L",
              "agama": "ISLAM", "pekerjaan": null, "status_perkawinan": "BELUM_KAWIN",
              "kewarganegaraan": "WNI", "dusun": "PERAMPUAN", "rt": "002", "rw": null, "alamat": null},
  "keperluan": "pengambilan rumah",
  "batas": [{"arah": "Utara"}],
  "uraian": "<p>...</p>"
}
```

Field `fields` di level atas (`data[<field key>]`); section penduduk/daftar/teks_bebas di `data[<section key>]`.
Saat render: kode pilihan → label, `ttl` = "Tempat, 3 November 1998", alamat disusun
"…, Dusun X, RT 002/RW 001, Desa …, Kecamatan …, Kabupaten …", rupiah = "Rp 1.500.000".

Buku Agenda Surat Keluar & Buku Register per jenis (Perbup Lombok Barat 87/2020 Pasal 9) **tidak punya tabel**:
dihasilkan dari `surat` yang bernomor (`GET /surat/agenda`, `GET /surat/register`).

## Role & permission (seed 002)

| Permission                                                                 | SUPER_ADMIN | ADMIN | SEKDES | KADES | PEGAWAI |
| -------------------------------------------------------------------------- | :---------: | :---: | :----: | :---: | :-----: |
| user.view, user.manage, user_role.assign                                   |     ✅      |  ✅   |        |       |         |
| login_failure.view                                                         |     ✅      |  ✅   |        |       |         |
| pegawai.view                                                               |     ✅      |  ✅   |   ✅   |  ✅   |         |
| pegawai.manage, pegawai.enroll_face                                        |     ✅      |  ✅   |        |       |         |
| jabatan / lokasi_kantor / jadwal_kerja / hari_libur / jenis_izin `.manage` |     ✅      |  ✅   |        |       |         |
| absensi.view_all                                                           |     ✅      |  ✅   |   ✅   |  ✅   |         |
| absensi.koreksi (migrasi 003)                                              |     ✅      |  ✅   |   ✅   |  ✅   |         |
| absensi_gagal.view (SEKDES/KADES: migrasi 010)                             |     ✅      |  ✅   |   ✅   |  ✅   |         |
| perizinan.view_all                                                         |     ✅      |  ✅   |   ✅   |  ✅   |         |
| perizinan.review                                                           |     ✅      |       |   ✅   |  ✅   |         |
| absensi.self, perizinan.self                                               |     ✅      |       |        |       |   ✅    |
| penduduk.view (SEKDES/KADES: migrasi 010)                                  |     ✅      |  ✅   |   ✅   |  ✅   |         |
| ref_option.manage, penduduk.manage (migrasi 005)                           |     ✅      |  ✅   |        |       |         |
| jenis_surat.manage (migrasi 005)                                           |     ✅      |  ✅   |        |       |         |
| surat.view (SEKDES/KADES: migrasi 010)                                     |     ✅      |  ✅   |   ✅   |  ✅   |         |
| surat.create, surat.terbitkan, surat.cancel (migrasi 005)                  |     ✅      |  ✅   |        |       |         |
| surat.edit_redaksi (migrasi 005)                                           |     ✅      |  ✅   |        |       |         |
| settings.surat_manage — pengaturan desa & surat (migrasi 007)              |     ✅      |  ✅   |        |       |         |

Nilai `roles.permissions`:

- **SUPER_ADMIN** — `["*"]` (developer; semua permission)
- **ADMIN** — `user.view, user.manage, user_role.assign, login_failure.view, pegawai.view, pegawai.manage,
pegawai.enroll_face, jabatan.manage, lokasi_kantor.manage, jadwal_kerja.manage, hari_libur.manage,
jenis_izin.manage, absensi.view_all, absensi_gagal.view, perizinan.view_all, absensi.koreksi` + persuratan:
`ref_option.manage, penduduk.view, penduduk.manage, jenis_surat.manage, surat.view, surat.create, surat.terbitkan,
surat.cancel, surat.edit_redaksi, settings.surat_manage` (tidak ada role OPERATOR: ADMIN merangkap operator surat)
- **SEKDES** — `pegawai.view, absensi.view_all, perizinan.view_all, perizinan.review, absensi.koreksi,
absensi_gagal.view, penduduk.view, surat.view` (lihat semua, tanpa master/pengaturan/akun)
- **KADES** — `pegawai.view, absensi.view_all, perizinan.view_all, perizinan.review, absensi.koreksi,
absensi_gagal.view, penduduk.view, surat.view` (lihat semua, tanpa master/pengaturan/akun)
- **PEGAWAI** — `absensi.self, perizinan.self`

Khusus SUPER_ADMIN (dicek di `users/service.py`, bukan lewat permission): memberi role ber-permission `*`,
mengubah/menonaktifkan/mengganti role & password akun SUPER_ADMIN, dan melihat kode pemulihan akun SUPER_ADMIN.

Arti: ADMIN mengurus data & akun tapi tidak meninjau perizinan (pengurus data ≠ pemberi persetujuan).
SEKDES = penyetuju harian & pemantau rekap. KADES = pemantau & peninjau perizinan milik Sekdes.
PEGAWAI = semua orang yang absen, termasuk Sekdes & Kades.

Penerapan saat ini:
| Orang | Role |
|---|---|
| Sekdes | PEGAWAI + SEKDES + ADMIN |
| Kades | PEGAWAI + KADES |
| Kaur, Kasi, Kadus | PEGAWAI |
| Developer | SUPER_ADMIN |

Sekdes berganti → hapus ADMIN dari user Sekdes baru, berikan ke staf yang ditunjuk.
