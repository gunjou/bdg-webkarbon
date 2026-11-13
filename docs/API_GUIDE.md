# Panduan API untuk Frontend — HRIS Desa Karang Bongkot

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
| Body | JSON, kecuali endpoint upload foto (`multipart/form-data`) |
| Waktu | ISO 8601 dengan zona WITA, mis. `2026-11-11T07:25:03+08:00` |
| Tanggal | `YYYY-MM-DD` · Jam (`jam_jadwal`, jadwal) `HH:MM` |
| Flag | `is_active`, `butuh_lampiran`, dll. = angka `1`/`0`, **bukan** boolean |
| Hapus | `DELETE` = **nonaktifkan** (soft delete). Aktifkan lagi: `POST .../{id}/activate` |
| Pagination | belum ada; list mengembalikan semua data aktif |

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
| `user.view` / `user.manage` | Akun non-pegawai | `/users...` |
| `user_role.assign` | Ubah role akun | `PUT /users/{id}/roles` |
| `jabatan.manage`, `lokasi_kantor.manage`, `jadwal_kerja.manage`, `jenis_izin.manage`, `hari_libur.manage` | Master data | `/master/<x>...` |

Role bawaan: `SUPER_ADMIN` (`*`), `ADMIN` (semua kecuali settings & review izin), `SEKDES`/`KADES`
(lihat pegawai & absensi, review izin), `PEGAWAI` (absen & izin sendiri). Satu akun bisa punya beberapa role;
permission-nya digabung (mis. Sekdes yang juga absen = `SEKDES` + `PEGAWAI`).

Aturan khusus yang akan ditolak backend (tampilkan `message`):
- ADMIN tidak bisa memberi role SUPER_ADMIN atau mengubah akun SUPER_ADMIN → `403`.
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
Lain: `400` field kurang, `413` foto > 5 MB, `403` akun tidak tertaut ke pegawai aktif.
Absen tidak bisa diubah/dihapus; koreksi lewat perizinan di bawah.

**Blokir presensi saat izin:** `GET /presensi/hari-ini` berisi `izin` = izin (bukan koreksi) berstatus
`diajukan`/`disetujui` yang mencakup hari ini, atau `null`. Jika tidak `null`, sembunyikan tombol absen dan tampilkan
`izin.jenis_izin_name` + `izin.status`. (Server tidak memblokir; aturan ini di frontend.)

### Perizinan pegawai (`perizinan.self`)

| Endpoint | Fungsi |
|---|---|
| `GET /presensi/jenis-izin` | Pilihan jenis izin aktif; `butuh_lampiran = 1` → lampiran wajib. |
| `POST /presensi/perizinan` (multipart) | Ajukan. Umum: `jenis_pengajuan` (`izin|koreksi`), `tanggal_mulai`, `alasan`, `lampiran?` (jpg/png/pdf, maks 5 MB; gambar dikompres ≤ 200 KB). **izin**: + `id_jenis_izin`, `tanggal_selesai` (default = mulai). **koreksi**: + `jenis_absen` (`masuk|pulang`), `jam_koreksi` (HH:MM). |
| `GET /presensi/perizinan?status=&tahun=` | Daftar pengajuan sendiri, terbaru di atas. |
| `GET /presensi/perizinan/{id}` | Detail, termasuk `catatan_peninjau`, `reviewed_by_name`. |
| `PUT /presensi/perizinan/{id}/batal` | Batalkan (hanya status `diajukan`). |
| `GET /presensi/perizinan/{id}/lampiran` | Unduh lampiran (`image/jpeg` / `application/pdf`). |

Aturan (`422` jika dilanggar): izin maks 30 hari & tidak beririsan dengan izin lain yang diajukan/disetujui;
koreksi hanya hari ini s/d 7 hari ke belakang, absen jenis itu belum tercatat, dan belum ada koreksi aktif yang sama.
Tidak ada ubah pengajuan: batalkan lalu ajukan ulang. Setuju/tolak dilakukan admin (modul terpisah, belum ada).

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

## 8. Gambar (foto)

Endpoint foto mengembalikan `image/jpeg` dan **butuh header Authorization**, jadi `<img src="...">` langsung
tidak bisa. Ambil sebagai blob:

```ts
const res = await api.get(`/pegawai/${id}/foto`, { responseType: "blob" });
const url = URL.createObjectURL(res.data);   // pakai di <img src={url}>, revoke saat unmount
```

`404` = foto belum ada. Jangan pakai `photo_path` dari respons sebagai URL — itu path internal server.

---

## 9. Ringkasan status HTTP

| Status | `code` umum | Arti |
|---|---|---|
| 200 / 201 | — | sukses |
| 400 | `VALIDATION_ERROR`, `BAD_REQUEST` | format input salah / field wajib kosong |
| 401 | `TOKEN_EXPIRED`, `TOKEN_MISSING`, `INVALID_TOKEN`, `UNAUTHORIZED` | lihat §2 |
| 403 | `FORBIDDEN` | tidak punya permission / aturan akses |
| 404 | `NOT_FOUND` | data atau endpoint tidak ada |
| 413 | `REQUEST_ENTITY_TOO_LARGE` | file > 5 MB |
| 422 | `VALIDATION_ERROR` atau kode bisnis (§4.3) | data valid secara format tapi ditolak aturan |
| 500 | `INTERNAL_ERROR` | error server; detail hanya di log backend |

---

## 10. Saat backend berubah

1. Backend: `venv/bin/python scripts/export_openapi.py` → commit `docs/openapi.json` (+ update dokumen ini bila
   alur/aturan berubah).
2. Frontend: `npx orval` → perbaiki error TypeScript yang muncul (itu tanda kontrak API berubah).
