# HRIS Desa Karang Bongkot — Backend API

Backend HRIS: login (users, role & permission) dan absensi berbasis **wajah + GPS**.

Flask · flask-restx · flask-jwt-extended · SQLAlchemy Core (raw SQL) · PostgreSQL · Python 3.10

## Fitur

| Modul   | Path        | Isi                                                                   |
| ------- | ----------- | --------------------------------------------------------------------- |
| auth    | `/auth`     | login (password / kode pemulihan), refresh token, `me`                |
| users   | `/users`    | akun & role                                                           |
| pegawai | `/pegawai`  | data pegawai + akun user + foto wajah                                 |
| absensi | `/absensi`  | absen masuk/pulang (wajah + GPS), status hari ini, riwayat, log gagal |
| master  | `/master/*` | jabatan, lokasi kantor, jadwal kerja, jenis izin, hari libur          |

## Setup

Prasyarat: Python 3.10, PostgreSQL, `cmake` + compiler C++ (untuk `dlib`), `libpq-dev`.

```bash
# Ubuntu: sudo apt install cmake build-essential libpq-dev
python3.10 -m venv venv
venv/bin/pip install -r requirements.txt

cp .env.example .env      # isi DB_* dan JWT_SECRET_KEY (≥32 byte)
python -c "import secrets; print(secrets.token_hex(32))"   # untuk JWT_SECRET_KEY
```

### Database

Jalankan migrasi berurutan secara manual:

```bash
psql -h <host> -U <user> -d <db> -f migrations/001_init.sql
psql -h <host> -U <user> -d <db> -f migrations/002_kode_pemulihan_dan_seed_roles.sql
```

Skema & daftar role: [SCHEMA.md](SCHEMA.md).

## Menjalankan

```bash
# development
venv/bin/flask --app api run --debug

# production
venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 api:app
```

Swagger UI: `http://<server>/docs`

## Environment

| Variabel                                                  | Keterangan                        |
| --------------------------------------------------------- | --------------------------------- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | koneksi PostgreSQL                |
| `JWT_SECRET_KEY`                                          | wajib, minimal 32 byte            |
| `JWT_ACCESS_EXPIRES`                                      | menit (default 60)                |
| `JWT_REFRESH_EXPIRES`                                     | hari (default 7)                  |
| `UPLOAD_DIR`                                              | folder upload (default `uploads`) |
| `MAX_UPLOAD_MB`                                           | batas upload (default 5)          |

## Dokumentasi API

- [docs/API_GUIDE.md](docs/API_GUIDE.md) — panduan untuk frontend
- [docs/openapi.json](docs/openapi.json) — spec OpenAPI (generate client, mis. `npx orval`)

Setelah mengubah endpoint/model, perbarui spec:

```bash
venv/bin/python scripts/export_openapi.py          # tulis ulang docs/openapi.json
venv/bin/python scripts/export_openapi.py --check  # exit 1 jika basi
```

## Struktur

```
api/
├── core/      config, database, security, storage
├── shared/    exceptions, response, error handler, docs
├── utils/     fungsi murni (waktu WITA, wajah, geo, ...)
└── modules/   auth, users, pegawai, absensi, master/*
migrations/    SQL berurutan
docs/          openapi.json + API_GUIDE.md
scripts/       export_openapi.py
```

Pola tiap modul: `endpoint → service → query`. Konvensi lengkap (respons, error, waktu WITA, DB) ada di [CLAUDE.md](CLAUDE.md).

## Catatan

- Semua waktu memakai WITA (`+08:00`) dari server.
- Waktu absen = jam server; aturan absensi lengkap di docstring `api/modules/absensi/service.py`.
- Belum ada pembatasan percobaan login (brute force).
