# Panduan API untuk Frontend — HRIS Desa Karang Bongkot

Dokumen ini menjelaskan **cara pakai** API. Daftar endpoint, body, dan bentuk respons yang lengkap ada di:

- **Swagger UI**: `<server>/docs` (bisa dicoba langsung)
- **Spec**: `docs/openapi.json` atau `<server>/swagger.json` → generate client React dengan `npx orval`

Jika dokumen ini berbeda dengan spec, **spec yang benar**. Aturan bisnis absen bersumber dari docstring
`api/modules/absensi/service.py`.

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
`errors`, `meta`, serta `masuk`/`pulang`/`jadwal` di `GET /absensi/hari-ini`. Selalu tangani `null`.

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
| `absensi.self` | Absen & riwayat saya | `/absensi/hari-ini`, `POST /absensi`, `/absensi/riwayat`, `POST /absensi/gagal` |
| `absensi.view_all` | Rekap absensi | `GET /absensi`, `/absensi/{id}`, `/absensi/{id}/foto` |
| `absensi_gagal.view` | Log absen gagal | `GET /absensi/gagal`, `/absensi/gagal/{id}/foto` |
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

## 4. Alur absen (aplikasi pegawai)

### 4.1 Layar absen

```
GET /absensi/hari-ini
```
Pakai respons ini untuk menyusun layar, **bukan** jam/tanggal HP:

| Field | Pakai untuk |
|---|---|
| `waktu_server` | jam yang ditampilkan |
| `pegawai.face_enrolled` | `false` → tombol absen nonaktif, pesan "Foto wajah belum didaftarkan, hubungi admin" |
| `hari_kerja`, `keterangan` | `false` → tampilkan `keterangan` (libur / bukan hari kerja / belum punya jadwal) |
| `jadwal.masuk_dibuka`, `jadwal.masuk`, `jadwal.pulang` | info jam & kapan tombol masuk aktif |
| `masuk`, `pulang` | `null` = belum; object = sudah (tampilkan jam & `status`) |
| `lokasi[]` | titik & radius kantor → peta / hitung jarak di client |
| `gps_max_akurasi_meter` | tunggu GPS sampai akurasi ≤ nilai ini sebelum kirim |

Tombol yang ditampilkan:
- `masuk == null` → tombol **Absen Masuk**
- `masuk != null && pulang == null` → tombol **Absen Pulang**
  (sebelum `jadwal.pulang` beri konfirmasi: "Belum jam pulang, tetap absen? (tercatat pulang cepat)")
- `masuk == null` dan sudah lewat `jadwal.pulang` → tombol **Absen Pulang** (lupa absen masuk; koreksi lewat perizinan)
- keduanya terisi → "Absen hari ini selesai"

### 4.2 Kirim absen

```
POST /absensi   (multipart/form-data)
  jenis        masuk | pulang
  latitude     number
  longitude    number
  akurasi_gps  number (meter, dari Geolocation API: coords.accuracy)
  foto         file selfie (jpg/png, maks 5 MB)
```

Urutan cek di server: **akun → jadwal → GPS → wajah**. Sukses = `201` berisi data absen
(`status`: `tepat_waktu` / `terlambat` / `pulang_cepat`, `terlambat_menit`).
Pengenalan wajah butuh ±1–2 detik → tampilkan loading & cegah tombol ditekan ulang.

### 4.3 Kode gagal absen (`422`)

Semua sudah tercatat otomatis di log server. Tampilkan `message`; `code` untuk logika UI.

| `code` | Tahap | Arti | Saran UI |
|---|---|---|---|
| `FACE_NOT_ENROLLED` | akun | belum ada foto wajah | minta hubungi admin |
| `HOLIDAY` | jadwal | hari libur | — |
| `NOT_WORKDAY` | jadwal | bukan hari kerja | — |
| `NO_SCHEDULE` | jadwal | pegawai belum punya jadwal | minta hubungi admin |
| `OUTSIDE_TIME_WINDOW` | jadwal | masuk belum dibuka / sudah ditutup | `message` berisi jamnya |
| `ALREADY_CHECKED` | jadwal | sudah absen jenis ini hari ini | muat ulang `/hari-ini` |
| `NOT_CHECKED_IN` | jadwal | pulang sebelum jam pulang tanpa absen masuk | arahkan ke absen masuk |
| `GPS_LOW_ACCURACY` | GPS | akurasi > batas | "Pindah ke area terbuka", coba lagi |
| `NO_OFFICE_LOCATION` | lokasi | lokasi kantor belum diatur | hubungi admin |
| `OUTSIDE_RADIUS` | lokasi | di luar radius kantor | `message` berisi jarak & batas |
| `FACE_NOT_DETECTED` | wajah | tidak ada / lebih dari 1 wajah / bukan gambar | ambil ulang foto, wajah sendiri, cahaya cukup |
| `FACE_NOT_MATCH` | wajah | wajah tidak cocok | ambil ulang; jika terus gagal hubungi admin |

Error lain: `400` (field form kurang/salah), `413` (foto > 5 MB → kompres dulu di client), `403` (akun tidak
tertaut ke pegawai aktif).

### 4.4 Laporkan kegagalan di HP

Kegagalan yang terjadi **sebelum** request terkirim tidak terlihat server. Laporkan:

```
POST /absensi/gagal   (JSON)
{ "stage": "GPS", "error_code": "GPS_PERMISSION_DENIED", "jenis": "masuk",
  "error_message": "User menolak izin lokasi", "detail": { "app_version": "1.0.0" } }
```

`stage`: `GPS | CAMERA | LOCATION | FACE`. `error_code`: huruf besar/angka/`_`, bebas tapi konsisten. Disarankan:
`GPS_PERMISSION_DENIED`, `GPS_TIMEOUT`, `GPS_UNAVAILABLE`, `CAMERA_PERMISSION_DENIED`, `CAMERA_UNAVAILABLE`,
`NETWORK_ERROR`. Kirim tanpa menunggu (fire-and-forget); gagal kirim boleh diabaikan.

### 4.5 Riwayat & rekap

```
GET /absensi/riwayat?tanggal_mulai=2026-11-01&tanggal_selesai=2026-11-30     (milik sendiri)
GET /absensi?tanggal_mulai=...&tanggal_selesai=...&id_pegawai=7             (absensi.view_all)
GET /absensi/gagal?tanggal_mulai=...                                         (absensi_gagal.view, maks 1000 baris)
```
Default = hari ini. Rentang maksimal **62 hari** (lebih → `422`).
Absensi **tidak bisa diubah/dihapus**; koreksi lewat modul perizinan (belum tersedia).

---

## 5. Pegawai (admin)

- `POST /pegawai` = **multipart/form-data**: data pegawai + akun login sekaligus, foto opsional.
  - Wajib: `full_name`, `id_jabatan`, `username`, `password` (≥ 8).
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

## 6. Master data

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

## 7. Gambar (foto)

Endpoint foto mengembalikan `image/jpeg` dan **butuh header Authorization**, jadi `<img src="...">` langsung
tidak bisa. Ambil sebagai blob:

```ts
const res = await api.get(`/pegawai/${id}/foto`, { responseType: "blob" });
const url = URL.createObjectURL(res.data);   // pakai di <img src={url}>, revoke saat unmount
```

`404` = foto belum ada. Jangan pakai `photo_path` dari respons sebagai URL — itu path internal server.

---

## 8. Ringkasan status HTTP

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

## 9. Saat backend berubah

1. Backend: `venv/bin/python scripts/export_openapi.py` → commit `docs/openapi.json` (+ update dokumen ini bila
   alur/aturan berubah).
2. Frontend: `npx orval` → perbaiki error TypeScript yang muncul (itu tanda kontrak API berubah).
