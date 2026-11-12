# SCHEMA

Ringkasan dari `migrations/001_init.sql` + `002_kode_pemulihan_dan_seed_roles.sql`. PostgreSQL 13+.
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

## 2. Master kepegawaian & absensi

| Tabel         | Kolom utama                                                                                                | Catatan                                                           |
| ------------- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| jabatan       | id_jabatan, name, sort_order, + audit                                                                      | name unik case-insensitive                                        |
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
| id_lokasi_kantor | FK lokasi_kantor | NULL = boleh absen di semua lokasi aktif            |
| nip              | VARCHAR(30)      | unik jika diisi                                     |
| full_name        | VARCHAR(150)     |                                                     |
| phone            | VARCHAR(20)      |                                                     |
| photo_path       | VARCHAR(255)     | foto enrollment                                     |
| embedding        | REAL[]           | NULL = belum enrollment wajah (`FACE_NOT_ENROLLED`) |
| + audit          |                  |                                                     |

## 3. Transaksi absensi

### absensi — hanya absen BERHASIL, append-only

`id_absensi` BIGINT PK, `id_pegawai` FK, `id_lokasi_kantor` FK, `tanggal` DATE, `jenis` (`masuk|pulang`),
`waktu_absen` TIMESTAMPTZ, `latitude`, `longitude`, `akurasi_gps`, `jarak_meter`, `skor_wajah`,
`photo_path` (wajib), `jam_jadwal` TIME (snapshot), `terlambat_menit` (snapshot, ≥0),
`status` (`tepat_waktu|terlambat|pulang_cepat`), `created_at`.
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

## Role & permission (seed 002)

| Permission                                                                 | SUPER_ADMIN | ADMIN | SEKDES | KADES | PEGAWAI |
| -------------------------------------------------------------------------- | :---------: | :---: | :----: | :---: | :-----: |
| settings.manage, role.manage                                               |     ✅      |       |        |       |         |
| user.view, user.manage, user_role.assign                                   |     ✅      |  ✅   |        |       |         |
| login_failure.view                                                         |     ✅      |  ✅   |        |       |         |
| pegawai.view                                                               |     ✅      |  ✅   |   ✅   |  ✅   |         |
| pegawai.manage, pegawai.enroll_face                                        |     ✅      |  ✅   |        |       |         |
| jabatan / lokasi_kantor / jadwal_kerja / hari_libur / jenis_izin `.manage` |     ✅      |  ✅   |        |       |         |
| absensi.view_all                                                           |     ✅      |  ✅   |   ✅   |  ✅   |         |
| absensi_gagal.view                                                         |     ✅      |  ✅   |        |       |         |
| perizinan.view_all                                                         |     ✅      |  ✅   |   ✅   |  ✅   |         |
| perizinan.review                                                           |     ✅      |       |   ✅   |  ✅   |         |
| absensi.self, perizinan.self                                               |     ✅      |       |        |       |   ✅    |

Nilai `roles.permissions`:

- **SUPER_ADMIN** — `["*"]` (developer; semua permission)
- **ADMIN** — `user.view, user.manage, user_role.assign, login_failure.view, pegawai.view, pegawai.manage,
pegawai.enroll_face, jabatan.manage, lokasi_kantor.manage, jadwal_kerja.manage, hari_libur.manage,
jenis_izin.manage, absensi.view_all, absensi_gagal.view, perizinan.view_all`
- **SEKDES** — `pegawai.view, absensi.view_all, perizinan.view_all, perizinan.review`
- **KADES** — `pegawai.view, absensi.view_all, perizinan.view_all, perizinan.review`
- **PEGAWAI** — `absensi.self, perizinan.self`

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
