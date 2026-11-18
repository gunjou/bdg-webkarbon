# Panduan API untuk Frontend — Sistem Kantor Desa Karang Bongkot

Dokumen ini menjelaskan **cara pakai** API. Daftar endpoint, body, dan bentuk respons yang lengkap ada di:

- **Swagger UI**: `<server>/docs` (bisa dicoba langsung)
- **Spec**: `docs/openapi.json` atau `<server>/swagger.json` → generate client React dengan `npx orval`

Jika dokumen ini berbeda dengan spec, **spec yang benar**.

---

## 1. Dasar

| Hal | Ketentuan |
|---|---|
| Base URL | diatur per environment di frontend (mis. `VITE_API_URL`), tidak ada di spec |
| Auth | header `Authorization: Bearer <access_token>` |
| Body | JSON, kecuali endpoint upload file (foto, lampiran, logo, scan arsip: `multipart/form-data`) |
| Waktu | ISO 8601 dengan zona WITA, mis. `2026-11-11T07:25:03+08:00` |
| Tanggal | `YYYY-MM-DD` · Jam (`jam_jadwal`, jadwal) `HH:MM` |
| Flag | `is_active`, `butuh_lampiran`, dll. = angka `1`/`0`, **bukan** boolean |
| Hapus | `DELETE` = **nonaktifkan** (soft delete). Aktifkan lagi: `POST .../{id}/activate` |
| Pagination | umumnya belum ada (list = semua data aktif). `GET /penduduk` & `GET /surat`: `limit` (default 50, maks 200) + `offset` |

**Field boleh `null`** (spec Swagger 2.0 tidak bisa menandainya): semua field opsional seperti `email`, `nip`,
`phone`, `photo_path`, `updated_at`, `updated_by`, `last_login_at`, `id_pegawai`, `full_name` (akun non-pegawai),
`errors`, `meta`. Selalu tangani `null`.

### Format respons

Sukses:
```json
{ "code": 200, "success": true, "message": "Login berhasil", "data": { }, "meta": { "execution_time_ms": 12.3 } }
```

Gagal (semua error, termasuk token & validasi):
```json
{ "success": false, "message": "Validasi gagal", "code": "VALIDATION_ERROR", "errors": { "username": "Sudah dipakai" } }
```

- `message` → **boleh langsung ditampilkan ke user** (Bahasa Indonesia).
- `code` → untuk logika di frontend (jangan cocokkan teks `message`).
- `errors` → detail per field untuk form (object), atau `null`.

---

## 2. Login & token

```
POST /auth/login     { username, password }   → access_token, refresh_token, user
POST /auth/refresh   { refresh_token }        → access_token baru
GET  /auth/me                                 → user (roles & permissions terbaru)
```

- Field `password` menerima **password ATAU kode pemulihan** (6 karakter dari admin). Tidak perlu UI terpisah,
  cukup beri teks bantuan "Lupa password? Masukkan kode pemulihan dari admin".
- Kredensial salah selalu `401` dengan pesan sama ("Username atau kredensial salah") — memang disengaja.
- `403` saat login = akun nonaktif / pegawai nonaktif / belum punya role → tampilkan `message`.
- **Logout** = hapus token di client. Tidak ada endpoint logout.
- Simpan `user.permissions` untuk menampilkan menu (lihat §3). Panggil `GET /auth/me` saat app dibuka
  agar permission selalu terbaru.

### Penanganan 401 (pasang di interceptor axios)

| `code` | Arti | Tindakan |
|---|---|---|
| `TOKEN_EXPIRED` | access token kedaluwarsa | panggil `/auth/refresh`, ulangi request sekali |
| `TOKEN_MISSING`, `INVALID_TOKEN` | token tidak ada/rusak | arahkan ke login |
| `UNAUTHORIZED` | login gagal / akun tidak ditemukan | tampilkan `message` |

Jika `/auth/refresh` sendiri gagal (401/403) → hapus token, arahkan ke login.
Refresh membaca ulang role & status akun dari DB, jadi perubahan role oleh admin berlaku setelah refresh.

```ts
// sketsa interceptor
api.interceptors.response.use(undefined, async (err) => {
  const { config, response } = err;
  if (response?.data?.code === "TOKEN_EXPIRED" && !config._retry) {
    config._retry = true;
    const { data } = await axios.post(`${BASE}/auth/refresh`, { refresh_token: getRefresh() });
    setAccess(data.data.access_token);
    config.headers.Authorization = `Bearer ${data.data.access_token}`;
    return api(config);
  }
  if (response?.status === 401) logoutAndRedirect();
  throw err;
});
```

---

## 3. Permission → menu

Tampilkan menu berdasarkan `user.permissions`. **`"*"` = boleh semua** (SUPER_ADMIN).
Backend tetap mengecek; menyembunyikan menu hanya untuk UX.

| Permission | Menu / fitur | Endpoint |
|---|---|---|
| `absensi.self` | **Aplikasi ABSEN**: presensi saya | `GET /presensi/hari-ini`, `POST /presensi`, `POST /presensi/gagal`, `GET /presensi/riwayat`, `/presensi/{id}/foto` |
| `perizinan.self` | **Aplikasi ABSEN**: pengajuan izin & koreksi saya | `GET /presensi/jenis-izin`, `GET/POST /presensi/perizinan`, `/presensi/perizinan/{id}`, `PUT /presensi/perizinan/{id}/batal`, `/presensi/perizinan/{id}/lampiran` |
| `absensi.view_all` | **Aplikasi ADMIN**: monitoring & rekap presensi | `GET /absensi/harian`, `/absensi/rekap`, `/absensi`, `/absensi/{id}`, `/absensi/{id}/foto` |
| `absensi.koreksi` | **Aplikasi ADMIN**: koreksi absen | `PUT /absensi/koreksi` |
| `absensi_gagal.view` | **Aplikasi ADMIN**: log absen gagal | `GET /absensi/gagal`, `/absensi/gagal/{id}/foto` |
| `perizinan.view_all` | **Aplikasi ADMIN**: daftar pengajuan | `GET /absensi/perizinan`, `/absensi/perizinan/{id}`, `/absensi/perizinan/{id}/lampiran` |
| `perizinan.review` | **Aplikasi ADMIN**: setujui/tolak, tambah izin pegawai | `PUT /absensi/perizinan/{id}/review`, `POST /absensi/perizinan` |
| `pegawai.view` | Daftar pegawai | `GET /pegawai`, `/pegawai/{id}`, `/pegawai/{id}/foto` |
| `pegawai.manage` | Tambah/ubah/nonaktifkan pegawai, ganti password | `POST/PUT/DELETE /pegawai...`, `PUT /pegawai/{id}/password` |
| `pegawai.enroll_face` | Ganti foto wajah | `PUT /pegawai/{id}/foto` |
| `user.view` / `user.manage` | Akun & role semua pengguna (pegawai & non-pegawai). Buat/ubah/nonaktif via `/users` hanya untuk akun non-pegawai; data akun pegawai lewat `/pegawai` | `GET /users?include_inactive=` (`id_pegawai`/`full_name` null = non-pegawai), `POST /users` `{username, email?, password, id_roles}` |
| `user_role.assign` | Ubah role akun | `PUT /users/{id}/roles`; pilihan role: `GET /users/roles` (juga untuk `user.manage` / `pegawai.manage`; role SUPER_ADMIN hanya tampil untuk SUPER_ADMIN) |
| `jabatan.manage`, `lokasi_kantor.manage`, `jadwal_kerja.manage`, `jenis_izin.manage`, `hari_libur.manage` | Master data | `/master/<x>...` |
| `ref_option.manage` | Master daftar pilihan (agama, pekerjaan, dusun, ...) | `POST/PUT/DELETE /master/ref-options...` |
| `penduduk.view` / `penduduk.manage` | Menu Penduduk | `GET /penduduk...` / `POST/PUT/DELETE /penduduk...` |
| `settings.surat_manage` | Pengaturan desa (kop) & penomoran surat | `PUT /settings`, `POST /settings/logo` |
| `perizinan.view_all` / `surat.view` / `surat.create` | Badge notifikasi di header | `GET /notifikasi` → `{perizinan: {jumlah, items[5]} \| null, surat: {jumlah, items[5]} \| null}`. `perizinan` = pengajuan izin/koreksi `diajukan` **tanpa milik akun sendiri**; `surat` = draft. `null` = tanpa akses (sembunyikan tombolnya). Ringan (COUNT), aman dipanggil berkala. |
| `jenis_surat.manage` | Kelola jenis surat (wizard form + redaksi) | `/jenis-surat...` (tulis), `/jenis-surat/placeholder`, `/jenis-surat/preview` |
| `surat.view` | Daftar & detail surat, PDF, agenda, register | `GET /surat...`, `/surat/{id}/pdf`, `/surat/agenda`, `/surat/register` |
| `surat.create` | Buat & isi draft, lampiran, surat pengganti | `POST /surat`, `PUT /surat/{id}`, `/surat/{id}/lampiran`, `POST /surat/{id}/pengganti` |
| `surat.edit_redaksi` | Sesuaikan redaksi per surat | `PUT/DELETE /surat/{id}/redaksi`, field `redaksi` di perbaikan, `POST /jenis-surat/placeholder` (panel editor) |
| `surat.terbitkan` | Terbitkan nomor, perbaikan, upload scan arsip | `POST /surat/{id}/terbitkan`, `/perbaiki`, `/arsip` |
| `surat.cancel` | Batalkan surat | `POST /surat/{id}/batal` |

Data pilihan & pencarian yang dibutuhkan form surat juga terbuka untuk `surat.create`/`surat.view`:
`GET /master/ref-options`, `GET /penduduk`, `GET /penduduk/{id}`, `GET /settings`, `GET /jenis-surat...`.

Role bawaan: `SUPER_ADMIN` (`*`), `ADMIN` (semua kecuali review izin & absen sendiri; termasuk
seluruh persuratan — tidak ada role OPERATOR terpisah), `SEKDES`/`KADES`
(lihat pegawai & absensi, review izin), `PEGAWAI` (absen & izin sendiri). Satu akun bisa punya beberapa role;
permission-nya digabung (mis. Sekdes yang juga absen = `SEKDES` + `PEGAWAI`).

Aturan khusus yang akan ditolak backend (tampilkan `message`):
- ADMIN tidak bisa memberi role SUPER_ADMIN atau mengubah akun SUPER_ADMIN → `403`.
- `GET /users/{id}` akun SUPER_ADMIN: `kode_pemulihan` = `null` bila peminta bukan SUPER_ADMIN.
- Tidak bisa menonaktifkan akun sendiri → `422`.

---

## 4. Presensi (aplikasi ABSEN, pegawai)

Semua endpoint butuh `absensi.self`; data selalu milik akun di token. Aturan lengkap: docstring
`api/modules/presensi/service.py`.

| Endpoint | Fungsi |
|---|---|
| `GET /presensi/hari-ini` | Layar absen: `waktu_server` (pakai ini, bukan jam HP), `pegawai.face_enrolled`, `hari_kerja` + `keterangan`, `jadwal` (`masuk_dibuka`, `masuk`, `pulang`), `masuk`/`pulang` (`null` = belum), `gps_max_akurasi_meter` (tunggu GPS sampai `coords.accuracy` ≤ nilai ini sebelum kirim). |
| `POST /presensi` (multipart) | Absen: `jenis` (`masuk|pulang`), `latitude`, `longitude`, `akurasi_gps`, `foto`. Cek: akun → jadwal → GPS → wajah. `201` berisi `status` (`tepat_waktu|terlambat|pulang_cepat`) & `terlambat_menit`. |
| `POST /presensi/gagal` (JSON) | Lapor gagal sebelum request terkirim: `stage` (`GPS|CAMERA|LOCATION|FACE`), `error_code` (mis. `GPS_PERMISSION_DENIED`), `jenis`, `error_message`, `detail`. Fire-and-forget. |
| `GET /presensi/riwayat?tanggal_mulai&tanggal_selesai` | Riwayat sendiri. Default awal bulan ini s/d hari ini, maks 62 hari. `is_koreksi = true` → absen dikoreksi admin (beri label). |
| `GET /presensi/{id}/foto` | Foto selfie absen sendiri (milik orang lain → 404). |

Tombol: `masuk == null` → **Absen Masuk**; `masuk != null && pulang == null` → **Absen Pulang**
(sebelum `jadwal.pulang` beri konfirmasi pulang cepat); `masuk == null` dan sudah lewat `jadwal.pulang` →
**Absen Pulang** (lupa masuk, koreksi lewat perizinan); keduanya terisi → selesai.
Lokasi sah = lokasi kantor aktif terdekat (semua lokasi aktif berlaku untuk semua pegawai).

Kode gagal `422` (sudah tercatat di server; tampilkan `message`):
`FACE_NOT_ENROLLED`, `HOLIDAY`, `NOT_WORKDAY`, `NO_SCHEDULE`, `OUTSIDE_TIME_WINDOW`, `ALREADY_CHECKED`,
`NOT_CHECKED_IN`, `GPS_LOW_ACCURACY`, `NO_OFFICE_LOCATION`, `OUTSIDE_RADIUS`, `FACE_NOT_DETECTED`, `FACE_NOT_MATCH`.
Lain: `400` field kurang, `413` foto > 10 MB, `403` akun tidak tertaut ke pegawai aktif.
Absen tidak bisa diubah/dihapus; koreksi lewat perizinan di bawah.

**Blokir presensi saat izin:** `GET /presensi/hari-ini` berisi `izin` = izin (bukan koreksi) berstatus
`diajukan`/`disetujui` yang mencakup hari ini, atau `null`. Jika tidak `null`, sembunyikan tombol absen dan tampilkan
`izin.jenis_izin_name` + `izin.status`. (Server tidak memblokir; aturan ini di frontend.)

### Perizinan pegawai (`perizinan.self`)

| Endpoint | Fungsi |
|---|---|
| `GET /presensi/jenis-izin` | Pilihan jenis izin aktif; `butuh_lampiran = 1` → lampiran wajib. |
| `POST /presensi/perizinan` (multipart) | Ajukan. Umum: `jenis_pengajuan` (`izin|koreksi`), `tanggal_mulai`, `alasan`, `lampiran?` (jpg/png/pdf, maks 10 MB; gambar dikompres ≤ 200 KB). **izin**: + `id_jenis_izin`, `tanggal_selesai` (default = mulai). **koreksi**: + `jenis_absen` (`masuk|pulang`), `jam_koreksi` (HH:MM). |
| `GET /presensi/perizinan?status=&tahun=` | Daftar pengajuan sendiri, terbaru di atas. |
| `GET /presensi/perizinan/{id}` | Detail, termasuk `catatan_peninjau`, `reviewed_by_name`. |
| `PUT /presensi/perizinan/{id}/batal` | Batalkan (hanya status `diajukan`). |
| `GET /presensi/perizinan/{id}/lampiran` | Unduh lampiran (`image/jpeg` / `application/pdf`). |

Aturan (`422` jika dilanggar): izin maks 30 hari & tidak beririsan dengan izin lain yang diajukan/disetujui;
koreksi hanya hari ini s/d 7 hari ke belakang, absen jenis itu belum tercatat, dan belum ada koreksi aktif yang sama.
Tidak ada ubah pengajuan: batalkan lalu ajukan ulang. Setuju/tolak dilakukan admin lewat `PUT /absensi/perizinan/{id}/review` (§5).

---

## 5. Absensi (aplikasi ADMIN)

Aturan lengkap: docstring `api/modules/absensi/service.py`.

| Endpoint | Fungsi |
|---|---|
| `GET /absensi/harian?tanggal=` | Semua pegawai aktif + `status_hari` (`hadir|izin|libur|bukan_hari_kerja|alpha|belum_absen`), `masuk`, `pulang`, `izin` (diajukan/disetujui), `jadwal` (`{masuk, pulang}` hari itu, `null` = bukan hari kerja), `keterangan` (nama hari libur). Dashboard "siapa belum hadir". |
| `GET /absensi/rekap?bulan=YYYY-MM&id_pegawai=` | Rekap per pegawai: `hari_kerja, hadir, terlambat, terlambat_menit, pulang_cepat, tanpa_masuk, tanpa_pulang, izin, izin_per_jenis, alpha, libur`. Bulan berjalan dihitung s/d hari ini. |
| `GET /absensi?tanggal_mulai&tanggal_selesai&id_pegawai&status` | Daftar absen (default hari ini, maks 62 hari). |
| `GET /absensi/{id}`, `/absensi/{id}/foto` | Detail & foto selfie (absen hasil koreksi tidak punya foto → `has_photo=false`). |
| `PUT /absensi/koreksi` (JSON) | Buat/timpa absen: `id_pegawai, tanggal, jenis, jam`. `status`, `terlambat_menit` & `jam_jadwal` dihitung dari jadwal pegawai (aturan sama dgn presensi). Hari libur / bukan hari kerja → `422`. |
| `GET /absensi/gagal?...&error_code=`, `/absensi/gagal/{id}/foto` | Log absen gagal (maks 1000) & foto wajah tidak cocok. |
| `GET /absensi/perizinan?status&jenis_pengajuan&id_pegawai&tanggal_mulai&tanggal_selesai` | Daftar pengajuan. Default `status=diajukan` (antrean); `status=semua` untuk semua. |
| `GET /absensi/perizinan/{id}`, `/lampiran` | Detail & lampiran. |
| `POST /absensi/perizinan` (multipart) | Admin menambah izin untuk pegawai: `id_pegawai, id_jenis_izin, tanggal_mulai, tanggal_selesai?, alasan, lampiran?`. Aturan sama dgn pengajuan pegawai (maks 30 hari, tidak bentrok, lampiran jika wajib); langsung `disetujui`, peninjau = admin. Akses `perizinan.review`. |
| `PUT /absensi/perizinan/{id}/review` (JSON) | `status` (`disetujui|ditolak`), `catatan_peninjau` (wajib jika ditolak). Koreksi disetujui → absen tercatat otomatis, status dihitung dari jadwal (hari libur → `422`). Tidak boleh meninjau pengajuan sendiri (403). |

`is_koreksi = true` pada absen = dibuat/diubah oleh akun selain pegawai itu sendiri (tampilkan label "Koreksi").
Alpha = hari kerja (jadwal pegawai saat ini, bukan libur) yang sudah lewat tanpa absen dan tanpa izin disetujui.

---

## 6. Pegawai (admin)

- `POST /pegawai` = **multipart/form-data**: data pegawai + akun login sekaligus, foto opsional.
  - Wajib: `full_name`, `id_jabatan`, `username`, `password` (≥ 5).
  - Opsional: `id_jadwal_kerja` (default 1), `nip`, `phone`, `email`, `id_roles` (kirim berulang:
    `id_roles=3&id_roles=5`; kosong = PEGAWAI), `foto`.
  - Respons berisi pegawai + user. **Tampilkan `kode_pemulihan` ke admin** lewat `GET /users/{id_user}` bila perlu.
- `PUT /pegawai/{id}` = JSON, data umum pegawai + user (tanpa password). `id_roles` dikosongkan = role tidak diubah.
- `PUT /pegawai/{id}/password` = ganti password.
- `PUT /pegawai/{id}/foto` = ganti foto wajah. Foto harus berisi **tepat 1 wajah** (`422` jika tidak).
- `DELETE /pegawai/{id}` menonaktifkan pegawai **dan** akunnya (tidak bisa login).
- `has_face: false` → tandai di daftar "belum bisa absen".

Form validasi: tampilkan `errors[field]` di bawah input yang sesuai.

---

## 7. Master data

Pola sama untuk `/master/jabatan`, `/master/lokasi-kantor`, `/master/jadwal-kerja`, `/master/jenis-izin`,
`/master/hari-libur`: `GET` list (aktif saja), `POST`, `GET/PUT/DELETE /{id}`, `POST /{id}/activate`.

Catatan per master:
- **Jabatan / jenis izin**: nama/kode unik termasuk yang nonaktif → pesan menyarankan aktifkan kembali.
- **Lokasi kantor**: `latitude` −90..90, `longitude` −180..180, `radius_meter` ≥ 1 (default 100).
- **Jadwal kerja**: `jadwal_harian` per hari `{ "masuk": "07:30", "pulang": "15:30" }` atau `null` (libur);
  hari yang tidak dikirim = libur. Error per hari di `errors.<hari>`.
- **Jenis izin**: `code` huruf/angka/`_`, disimpan HURUF BESAR.
- **Hari libur**: `GET ?tahun=2026` untuk filter; 1 tanggal = 1 libur aktif.
- Nonaktifkan ditolak (`422`) jika masih dipakai pegawai aktif (jabatan, lokasi, jadwal) atau pengajuan
  berstatus diajukan (jenis izin).

---

## 8. Persuratan (aplikasi ADMIN)

Sistem hanya sampai **penerbitan nomor**. Pengesahan tetap manual: surat dicetak, ditandatangani basah, distempel,
lalu scan-nya di-upload sebagai arsip. Skema & bentuk data lengkap: `SCHEMA.md` §4.

### 8.1 Data pendukung

| Endpoint | Fungsi |
|---|---|
| `GET /master/ref-options?group_code=AGAMA&include_inactive=0` | Pilihan dropdown. Simpan **`code`**, tampilkan `label`. Grup: `AGAMA, PEKERJAAN, STATUS_PERKAWINAN, KEWARGANEGARAAN, DUSUN, PENDIDIKAN, HUBUNGAN_KELUARGA`. |
| `POST/PUT/DELETE /master/ref-options...`, `POST .../{id}/activate` | Kelola pilihan. `is_system = 1` (bawaan): kode & grup tidak bisa diubah, tidak bisa dinonaktifkan (`422`); label & urutan boleh. |
| `GET /penduduk?q=&dusun=&include_inactive=&limit=&offset=` | Cari warga. `q` angka = awalan NIK / No. KK; selain itu = awalan nama. |
| `GET/POST/PUT/DELETE /penduduk...`, `POST /penduduk/{id}/activate` | Kelola warga. Field opsional boleh `null`/`""`. NIK & No. KK 16 digit, NIK unik. RT/RW otomatis 3 digit. Kode pilihan baru harus aktif; kode lama yang tidak diganti tetap diterima walau opsinya sudah nonaktif. |
| `GET /settings` | `{ "desa.nama": ..., "surat.format_nomor": ..., ... }` (key lihat SCHEMA.md). |
| `PUT /settings` | Kirim **hanya key yang diubah**. Error per key di `errors["surat.format_nomor"]`, dst. |
| `GET /settings/logo`, `POST /settings/logo` (multipart `logo`) | Logo kop. Belum upload → logo Kabupaten Lombok Barat bawaan (`image/svg+xml`); sudah → `image/png` (diperkecil ≤ 600 px). |
| `GET/PUT /master/jabatan...` field `can_sign` | `1` = pejabat boleh menandatangani surat. Tidak dikirim saat PUT = nilai lama tetap. |

### 8.2 Jenis surat (wizard 4 langkah)

| Endpoint | Fungsi |
|---|---|
| `GET /jenis-surat?include_inactive=` | Daftar ringkas (tanpa skema & redaksi). |
| `GET /jenis-surat/{id}` | Lengkap: `skema_form`, `template_isi`, `persyaratan`, `versi`. |
| `POST /jenis-surat/placeholder` `{skema_form}` | Isi panel placeholder editor dari skema yang **belum disimpan** (langkah 3): `[{token, label, group}]`. |
| `POST /jenis-surat/preview` `{name, skema_form, template_isi}` | PDF data contoh + watermark CONTOH (langkah 4). |
| `POST /jenis-surat`, `PUT /jenis-surat/{id}` | Simpan. `template_isi` kosong = redaksi standar desa. `versi` naik bila skema/redaksi berubah. |
| `POST /jenis-surat/{id}/duplikat` `{code, name}` | Salin skema, redaksi & persyaratan ke jenis baru (versi 1). |
| `DELETE /jenis-surat/{id}`, `POST .../activate` | Nonaktif / aktif. |

Langkah wizard: (1) info dasar `code, name, kode_klasifikasi, persyaratan, sort_order` → (2) susun `skema_form`
→ (3) redaksi → (4) preview & simpan.

**Editor redaksi (TipTap)**: tampilkan placeholder sebagai *chip* yang tidak bisa diketik; saat simpan, chip
diubah jadi teks `token` apa adanya (mis. `{{ biodata(pemohon) }}`). Tag yang bertahan: `p b strong i em u br table
tbody tr td th ul ol li span`; style hanya `text-align, font-weight, font-style, text-decoration, width,
text-indent`. Blok `{% %}` ditolak. Error validasi: `errors.template_isi` ("Tidak dikenal: nama_ibu", "Baris 1: ...").
Error skema per path, mis. `errors["skema_form.sections[1].fields[0].key"]` → tandai field yang sesuai.

### 8.3 Alur surat

```
POST /surat ─► draft ──PUT /surat/{id} (isi, penandatangan)──► POST /terbitkan ─► diterbitkan
                │                                                                 │  POST /perbaiki (nomor tetap)
                │                                                                 │  POST /arsip  ─► terkunci
                └────────── POST /batal {alasan} ───────────────┬──────────────────┘
                                                                ▼
                                                           dibatalkan ── POST /pengganti ─► draft baru
```

| Endpoint | Fungsi |
|---|---|
| `GET /surat?status=&id_jenis_surat=&tahun=&q=&limit=&offset=` | Daftar terbaru. `q` angka = awalan NIK pemohon, selain itu awalan nama. `terkunci` = scan arsip sudah ada. |
| `POST /surat` `{id_jenis_surat, data?}` | Buat draft (jenis surat harus aktif). |
| `GET /surat/{id}` | Detail: `skema_form` (render form dari sini, **bukan** dari jenis surat), `data`, `redaksi`, `lampiran`, `riwayat`, ... |
| `PUT /surat/{id}` `{data, id_penandatangan}` | Simpan draft. `data` dikirim **lengkap** (menimpa). `id_penandatangan` `null` / tidak dikirim = belum dipilih (menghapus pilihan lama). Hanya format yang dicek; field wajib dicek saat terbit. |
| `GET /surat/penandatangan` | Pilihan penandatangan + `atas_nama` (1 = dicetak "a.n Kepala Desa"). |
| `PUT /surat/{id}/redaksi` `{redaksi}` / `DELETE /surat/{id}/redaksi` | Sesuaikan redaksi surat ini (`redaksi_diubah = 1`) / kembalikan ke template standar. Hanya draft. |
| `POST /surat/{id}/lampiran` (multipart `nama`, `file`) | Lampiran pdf/jpg/png sesuai `persyaratan`. `GET/DELETE /surat/{id}/lampiran/{id_lampiran}`. |
| `GET /surat/{id}/pdf` | PDF: draft = watermark DRAF (belum bernomor); diterbitkan = PDF tersimpan (cetak ini); dibatalkan = watermark DIBATALKAN. (`/preview` = render ulang, tanpa PDF tersimpan.) |
| `POST /surat/{id}/terbitkan` | Ambil nomor & tanggal (hari ini). `422` bila isian belum lengkap (`errors` per field) atau penandatangan belum dipilih. |
| `POST /surat/{id}/perbaiki` `{catatan, data?, id_penandatangan?, redaksi?}` | Cetak ulang dengan nomor & tanggal sama, selama belum diarsip. `redaksi` butuh `surat.edit_redaksi` (`403`). |
| `POST /surat/{id}/arsip` (multipart `file`), `GET /surat/{id}/arsip` | Upload / unduh scan bertanda tangan. Setelah upload, perbaikan ditolak. |
| `POST /surat/{id}/batal` `{alasan}` | Batal. Nomor yang sudah terbit tetap tercatat & hangus (tidak dipakai lagi). |
| `POST /surat/{id}/pengganti` | Draft baru dari surat bernomor yang dibatalkan (isian & penandatangan disalin, lampiran tidak). Nomor baru didapat saat diterbitkan. |

**Bentuk `data`** (sesuai `skema_form` surat): field section `fields` di level atas (`data.keperluan`); section
`penduduk` / `daftar` / `teks_bebas` di `data[<key section>]`. Orang:
`{id_penduduk?, nama, nik, no_kk, tempat_lahir, tanggal_lahir, jenis_kelamin, agama, pekerjaan,
status_perkawinan, kewarganegaraan, dusun, rt, rw, alamat}`.

- Pilih dari pencarian `GET /penduduk` → salin field warga ke objek orang + `id_penduduk`. Operator tetap boleh
  mengoreksi isian (tersimpan sebagai snapshot di surat, tabel penduduk tidak berubah).
- Isi manual → `id_penduduk: null`. Warga manual **tidak** masuk ke tabel penduduk.
- `select` dengan `options_group` → kirim `code`; `rupiah` → angka; `date` → `YYYY-MM-DD`; `daftar` → array baris.
- Error isian: `errors["pemohon.nik"]`, `errors["keperluan"]`, `errors["batas[0].arah"]`.

Tombol per status: **draft** → Simpan, Preview, Terbitkan, Batal; **diterbitkan** & `terkunci = false` → Cetak
(`/pdf`), Perbaiki, Upload scan, Batal; **diterbitkan** & `terkunci = true` → Cetak, Lihat scan, Batal;
**dibatalkan** → Lihat PDF, Buat pengganti (bila bernomor & belum punya pengganti).

### 8.4 Buku agenda & register

| Endpoint | Fungsi |
|---|---|
| `GET /surat/agenda?tahun=` | Buku Agenda Surat Keluar: semua surat bernomor setahun (termasuk dibatalkan), urut tanggal. |
| `GET /surat/register?id_jenis_surat=&tahun=` | Buku Register per jenis: + `kolom` (field `register: true`) dan `rows[].kolom[<key>]`. |

Tiap baris: `no, nomor_surat, tanggal_surat, judul, nama_pemohon, nik_pemohon, status, penandatangan, diarsip,
keterangan` (mis. "DIBATALKAN – Salah nama; Diganti dengan 148.1/3/KRB/2026"). Ekspor PDF/Excel belum ada:
cetak dari tampilan tabel.

---

## 9. Gambar, PDF & file

Endpoint file (foto `image/jpeg`, logo, PDF surat, lampiran, scan arsip) **butuh header Authorization**, jadi
`<img src="...">` / `<iframe src="...">` langsung tidak bisa. Ambil sebagai blob:

```ts
const res = await api.get(`/pegawai/${id}/foto`, { responseType: "blob" });
const url = URL.createObjectURL(res.data);   // pakai di <img src={url}>, revoke saat unmount
```

```ts
const res = await api.get(`/surat/${id}/pdf`, { responseType: "blob" });
window.open(URL.createObjectURL(res.data));  // atau <iframe>; nama file ada di header Content-Disposition
```

`404` = file belum ada. Jangan pakai `photo_path` dari respons sebagai URL — itu path internal server (path file
surat memang tidak dikirim). Error pada endpoint blob tetap JSON: baca dengan `JSON.parse(await res.data.text())`.

---

## 10. Ringkasan status HTTP

| Status | `code` umum | Arti |
|---|---|---|
| 200 / 201 | — | sukses |
| 400 | `VALIDATION_ERROR`, `BAD_REQUEST` | format input salah / field wajib kosong |
| 401 | `TOKEN_EXPIRED`, `TOKEN_MISSING`, `INVALID_TOKEN`, `UNAUTHORIZED` | lihat §2 |
| 403 | `FORBIDDEN` | tidak punya permission / aturan akses |
| 404 | `NOT_FOUND` | data atau endpoint tidak ada |
| 413 | `REQUEST_ENTITY_TOO_LARGE` | file > 10 MB |
| 422 | `VALIDATION_ERROR` atau kode bisnis (§4.3) | data valid secara format tapi ditolak aturan |
| 500 | `INTERNAL_ERROR` | error server; detail hanya di log backend |

---

## 11. Saat backend berubah

1. Backend: `venv/bin/python scripts/export_openapi.py` → commit `docs/openapi.json` (+ update dokumen ini bila
   alur/aturan berubah).
2. Frontend: `npx orval` → perbaiki error TypeScript yang muncul (itu tanda kontrak API berubah).
