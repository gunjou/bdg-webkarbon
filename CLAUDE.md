# CLAUDE.md

HRIS backend Desa Karang Bongkot: login (users & roles) + absensi berbasis wajah & GPS.
Flask + flask-restx + flask-jwt-extended + SQLAlchemy Core (raw SQL via `text()`), PostgreSQL. Python 3.10.

Skema tabel & role: lihat [SCHEMA.md](SCHEMA.md). Sumber kebenaran skema: `migrations/*.sql`.

## Struktur

```
migrations/            SQL berurutan (001_, 002_, ...). Dijalankan manual dengan psql. Di root, bukan di api/.
docs/                  openapi.json (hasil generate, di-commit) + API_GUIDE.md (panduan frontend)
scripts/               export_openapi.py
uploads/               file upload (di-ignore git), lokasi dari UPLOAD_DIR
api/
├── __init__.py        hanya merakit app: Flask, JWT, Api, handler, daftar namespace modul
├── core/              infrastruktur (punya state / side effect)
│   ├── config.py      SATU-SATUNYA tempat baca env (load_dotenv sekali)
│   ├── database.py    get_engine() — engine lazy, URL.create (password aman dari karakter khusus)
│   ├── security.py    role_required, permission_required
│   └── storage.py     save_file, delete_file, full_path (tolak path di luar UPLOAD_DIR)
├── shared/            kontrak bersama semua modul
│   ├── exceptions.py  AppError + turunan (AuthError 401, ForbiddenError 403, NotFoundError 404,
│   │                  ValidationError 422, DatabaseError 500)
│   ├── response.py    success(), error() — format respons tunggal
│   ├── error_handlers.py  handler JWT, AppError, HTTPException, 404, 500
│   └── docs.py        api_doc, file_doc, audit_fields — dokumentasi respons OpenAPI
├── utils/             fungsi murni, tanpa Flask/DB/env
│   ├── datetime.py    get_wita()
│   ├── serializer.py  serialize_value()
│   ├── timing.py      measure_execution_time
│   ├── face.py        process_face_photo (1 wajah → jpeg + embedding 128), face_distance
│   └── geo.py         haversine_m
└── modules/           satu folder per modul bisnis (modular monolith)
    ├── auth/          login, refresh, me
    ├── users/         akun & role; juga validasi user untuk pegawai (prepare_new/prepare_update)
    ├── pegawai/       pegawai + akun user + foto wajah (selalu 1 pegawai = 1 user)
    ├── absensi/       aplikasi ADMIN: harian, rekap, log gagal, koreksi absen, review perizinan
    ├── presensi/      aplikasi ABSEN: absen wajah + GPS, riwayat, lapor gagal, perizinan & koreksi milik sendiri
    └── master/        sub-modul: jabatan, lokasi_kantor, jadwal_kerja, jenis_izin, hari_libur
```

Patokan letak kode: butuh env/DB/app → `core/`; aturan bersama antar modul → `shared/`;
fungsi murni yang bisa di-copy ke proyek lain → `utils/`; logika bisnis → `modules/`.

## Aturan modul (modular monolith)

Isi tiap modul:
- `__init__.py` — `ns = Namespace(...)` lalu `from . import endpoint`
- `schema.py` — `ns.model(...)` / `reqparse` untuk input, dan model output `<x>_out` untuk dokumentasi
- `endpoint.py` — HTTP saja: ambil request → panggil service → `return success(...)`. Tanpa SQL, tanpa logika bisnis.
- `service.py` — logika bisnis; gagal = `raise` turunan `AppError`
- `query.py` — SQL saja via `text()` + parameter bernama. Tanpa logika bisnis.

Arah import satu jalur: `endpoint → service → query`.
- Modul TIDAK boleh import `query` modul lain; pakai fungsi di `service.py` modul tersebut.
  Pengecualian yang disengaja: `pegawai/query.py` menulis tabel `users`/`user_roles` dalam SATU transaksi
  bersama pegawai (validasinya tetap lewat `users.service`). Jika kolom `users` berubah, ubah keduanya.
- `core/`, `shared/`, `utils/` TIDAK boleh import dari `modules/`.
- Modul induk dengan sub-modul (mis. `modules/master/jabatan/`): tiap sub-modul berisi 5 file yang sama +
  namespace sendiri; daftarkan di `NAMESPACES` pada `modules/master/__init__.py` (path `/master/<sub>`).
- Daftarkan namespace di bagian `MODULES` paling bawah `api/__init__.py`:
  `api.add_namespace(<x>_ns, path="/<x>")`.

## Respons & error

- Sukses: `return success(data, "pesan")` → `{code, success, message, data, meta}`.
- Gagal: `raise AppError`/turunannya. JANGAN `return error(...)` manual dari endpoint, JANGAN `abort()`.
- Format error selalu `{success: false, message, code, errors}`; termasuk JWT, validasi restx, 404, 500.
- Error 500 tidak membocorkan detail; detail hanya ke log.
- `@measure_execution_time` menaruh `meta.execution_time_ms`; pasang di bawah decorator auth.
- Setiap endpoint WAJIB `@api_doc(ns, <model_out>, many=..., status=..., errors=(...))` (`api/shared/docs.py`)
  paling atas; model output `<x>_out` di `schema.py`. Endpoint file pakai `@file_doc(ns)`. Ini sumber OpenAPI untuk frontend.
- Setelah mengubah endpoint/model: `venv/bin/python scripts/export_openapi.py` → commit `docs/openapi.json`
  (`--check` = exit 1 jika basi).

## Waktu (WAJIB)

Zona waktu lokal dev ≠ VPS. Semua waktu yang ditulis ke DB harus dari `get_wita()`:
- Isi kolom waktu lewat parameter: `{"now": get_wita()}`. JANGAN pakai `now()` SQL atau `datetime.now()`.
- `get_wita()` mengembalikan datetime AWARE (+08:00). JANGAN `.replace(tzinfo=None)` — kolom
  `TIMESTAMPTZ` menafsirkan naive memakai zona sesi DB → bergeser 8 jam di VPS UTC.
- Kolom `DATE` / `TIME`: `get_wita().date()` / `get_wita().time()`.
- Isi juga `created_at` secara eksplisit walau ada `DEFAULT now()`.

## Konvensi database

- PK `id_<entitas>` (IDENTITY); FK bernama sama dengan PK tujuan; peran lain pakai nama peran
  (`created_by`, `updated_by`, `reviewed_by` → `users.id_user`).
- Flag `SMALLINT` 0/1 (`is_active = 1` = aktif). Bandingkan dengan `== 1`, bukan truthy.
- `updated_at` / `updated_by` diisi aplikasi pada setiap UPDATE.
- Username/email unik case-insensitive → cari dengan `lower(kolom) = lower(:param)`.
- Baca: `with get_engine().connect()`. Tulis: `with get_engine().begin()` (auto commit/rollback).
- Hasil baris: `.mappings().first()` / `.mappings().all()`.
- Perubahan skema = file migrasi baru bernomor (idempoten: `IF NOT EXISTS`, `ON CONFLICT`), jangan edit 001.

## Auth & otorisasi

- Satu endpoint login untuk semua akun: `POST /auth/login` dengan `username` + `password`; field `password`
  dicek sebagai password dulu, jika salah dicek sebagai `kode_pemulihan`.
  Field `client` (`admin|absensi`, dikirim otomatis frontend): `admin` butuh permission selain
  `absensi.self`/`perizinan.self`; `absensi` butuh akun pegawai + `absensi.self`. Gagal → 403 `CLIENT_FORBIDDEN`.
  Respons `user`: admin → roles & permissions; absensi → data pegawai (nip, jabatan, face_enrolled).
- Juga `POST /auth/refresh` (body `{"refresh_token"}` atau header Bearer), `GET /auth/me`.
- `kode_pemulihan`: string acak 6 karakter, disimpan plain (keputusan pemilik; hanya admin yang bisa lihat).
  Bandingkan dengan `hmac.compare_digest`.
- Logout = hapus token di client. Tidak ada blocklist.
- Claim access token: `sub` = id_user (string), `id_pegawai`, `roles` (kode), `permissions` (gabungan).
  Refresh membaca ulang role & status akun dari DB.
- Endpoint dilindungi dengan `@permission_required("perizinan.review")` (utama) atau `@role_required("ADMIN")`.
  Utamakan permission agar pergantian jabatan cukup ubah data `user_roles`.
- Permission `"*"` (SUPER_ADMIN) lolos semua cek.
- Pesan gagal kredensial selalu sama ("Username atau kredensial salah") untuk cegah enumerasi username.
- Kegagalan login user terdaftar dicatat ke `login_failures` (WRONG_PASSWORD — password &
  kode pemulihan sama-sama salah, USER_INACTIVE, PEGAWAI_INACTIVE, NO_ACTIVE_ROLE, CLIENT_FORBIDDEN, SERVER_ERROR).
- Belum ada pembatasan percobaan login (brute force) — rencana: kunci setelah N gagal dari `login_failures`.

## Env (`.env`)

Template: `.env.example`. Hanya dibaca di `api/core/config.py`; env baru → tambah di config.py DAN `.env.example`.
`DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, JWT_SECRET_KEY (wajib, ≥32 byte),
JWT_ACCESS_EXPIRES (menit), JWT_REFRESH_EXPIRES (hari), UPLOAD_DIR (default uploads), MAX_UPLOAD_MB (default 5)`.

## Setup & dependency

- `python3.10 -m venv venv && venv/bin/pip install -r requirements.txt`.
- `dlib` (dipakai `face-recognition`) di-compile saat install: butuh `cmake` + compiler C++
  (Ubuntu: `apt install cmake build-essential`). `psycopg2` butuh `libpq-dev`.
- Paket baru → tambah ke `requirements.txt` dengan versi terkunci (`==`).

## Lain-lain

- Bahasa pesan ke user: Bahasa Indonesia. Kode error: UPPER_SNAKE_CASE bahasa Inggris.
- Jangan tulis data ke DB remote saat testing tanpa izin pemilik; uji service dengan mock `query`.

## Presensi

Ketentuan lengkap di docstring `api/modules/presensi/service.py` (sumber kebenaran). Ringkas: hanya untuk
pegawai (`absensi.self`), pegawai diambil dari token. Urutan cek akun → jadwal/libur → GPS → wajah, waktu =
jam server WITA, lokasi sah = lokasi kantor aktif terdekat (pegawai tidak diikat ke lokasi). Setiap gagal
dicatat ke `absensi_gagal`. `settings`: `ABSEN_MASUK_BUKA_MENIT` (60), `GPS_MAX_AKURASI_METER` (50),
`FACE_MATCH_THRESHOLD` (0.5). Perizinan pegawai (`perizinan.self`) juga di modul ini; `hari-ini.izin` dipakai
frontend untuk memblokir presensi (server tidak memblokir).

## Absensi (admin)

Ketentuan di docstring `api/modules/absensi/service.py`. Tabel `absensi` TIDAK lagi append-only murni:
koreksi (admin `absensi.koreksi` atau review koreksi disetujui) meng-upsert per (pegawai, tanggal, jenis) dan mengisi
`created_by`/`updated_by`. `is_koreksi` = pembuat/pengubah terakhir bukan akun pegawai itu (presensi mengisi
`created_by` = akun pegawai). `absensi_gagal` tetap append-only.
