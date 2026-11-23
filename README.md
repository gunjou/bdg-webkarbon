# HRIS Desa Karang Bongkot — Backend API

Backend sistem kantor Desa Karang Bongkot: login (users, role & permission), absensi berbasis **wajah + GPS**,
dan **persuratan** (data penduduk, cetakan surat, penerbitan nomor, PDF, buku agenda & register).

Flask · flask-restx · flask-jwt-extended · SQLAlchemy Core (raw SQL) · PostgreSQL · Python 3.10

## Fitur

| Modul   | Path        | Isi                                                                   |
| ------- | ----------- | --------------------------------------------------------------------- |
| auth    | `/auth`     | login (password / kode pemulihan), refresh token, `me`                |
| users   | `/users`    | akun & role                                                           |
| pegawai | `/pegawai`  | data pegawai + akun user + foto wajah                                 |
| presensi | `/presensi` | aplikasi absen pegawai: absen wajah + GPS, riwayat, perizinan sendiri |
| absensi | `/absensi`  | aplikasi admin: harian, rekap, log gagal, koreksi, review perizinan   |
| master  | `/master/*` | jabatan (+ `can_sign`), lokasi kantor, jadwal kerja, jenis izin, hari libur, ref-options (daftar pilihan) |
| penduduk | `/penduduk` | data induk warga + pencarian NIK/nama                                 |
| settings | `/settings` | pengaturan desa (kop surat, logo) & penomoran surat                   |
| jenis-surat | `/jenis-surat` | cetakan surat: skema form, redaksi, placeholder, preview PDF, duplikat |
| surat   | `/surat`    | draft, lampiran, penandatangan, terbit nomor, perbaikan, arsip, batal, pengganti, agenda & register |

## Setup

Prasyarat: Python 3.10, PostgreSQL, `cmake` + compiler C++ (untuk `dlib`), `libpq-dev`, pango (untuk WeasyPrint/PDF).

```bash
# Ubuntu: sudo apt install cmake build-essential libpq-dev libpango-1.0-0 libpangoft2-1.0-0
# macOS : brew install cmake pango
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
psql -h <host> -U <user> -d <db> -f migrations/003_koreksi_absensi.sql
psql -h <host> -U <user> -d <db> -f migrations/004_persuratan.sql
psql -h <host> -U <user> -d <db> -f migrations/005_permission_persuratan.sql
psql -h <host> -U <user> -d <db> -f migrations/006_seed_ref_options.sql
psql -h <host> -U <user> -d <db> -f migrations/007_permission_settings_surat.sql
psql -h <host> -U <user> -d <db> -f migrations/008_seed_jenis_surat_skbm.sql
psql -h <host> -U <user> -d <db> -f migrations/009_can_sign_dan_judul_surat.sql
```

Skema & daftar role: [SCHEMA.md](SCHEMA.md).

Setelah migrasi: isi opsi `PEKERJAAN` & `DUSUN` (menu master pilihan), cek pengaturan desa (kop surat), dan
pastikan pegawai Kepala Desa / Sekretaris Desa aktif (penandatangan surat).

### PDF surat (WeasyPrint)

- Butuh library sistem **pango** (lihat Prasyarat). Tanpa pango, aplikasi tetap jalan, hanya endpoint PDF yang gagal.
- **macOS**: Python venv tidak mencari library Homebrew. Jalankan backend dengan
  `export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` (taruh di `~/.zshrc`).
- Font surat dibundel (`api/assets/fonts/`, Liberation Serif — metrik sama dengan Times New Roman, lisensi SIL OFL),
  jadi hasil PDF sama di semua mesin tanpa memasang font di server.
- Kop: logo kiri (default `api/assets/logo-kabupaten.svg`) & kanan (default `api/assets/logo-desa.png`), keduanya bisa di-upload (`POST /settings/logo?posisi=kiri|kanan`).

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
| `JWT_MOBILE_EXPIRES`                                      | hari, token client mobile (default 365) |
| `UPLOAD_DIR`                                              | folder upload (default `uploads`) |
| `MAX_UPLOAD_MB`                                           | batas upload (default 10)         |

Reverse proxy (nginx) di depan gunicorn: set `client_max_body_size` ≥ `MAX_UPLOAD_MB` (mis. `10m`), karena
default nginx 1 MB menolak upload scan surat sebelum sampai ke aplikasi.

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
├── utils/     fungsi murni (waktu WITA, wajah, geo, template surat, ...)
├── assets/    logo kop & font PDF (ikut repo)
└── modules/   auth, users, pegawai, presensi, absensi, master/*, penduduk, settings, jenis_surat, surat
migrations/    SQL berurutan
tests/         unittest (DB di-mock): venv/bin/python -m unittest discover -s tests
docs/          openapi.json + API_GUIDE.md
scripts/       export_openapi.py
```

Pola tiap modul: `endpoint → service → query`. Konvensi lengkap (respons, error, waktu WITA, DB) ada di [CLAUDE.md](CLAUDE.md).

## Catatan

- Semua waktu memakai WITA (`+08:00`) dari server.
- Waktu absen = jam server; aturan presensi di docstring `api/modules/presensi/service.py`, absensi admin di
  `api/modules/absensi/service.py`.
- Aturan persuratan (snapshot, nomor, perbaikan, arsip, batal, pengganti) di docstring
  `api/modules/surat/service.py` dan `api/modules/jenis_surat/service.py`; skema di [SCHEMA.md](SCHEMA.md) §4.
- Pengesahan surat tetap manual (cetak, tanda tangan basah, stempel); sistem hanya sampai penerbitan nomor.
- Belum ada pembatasan percobaan login (brute force).
