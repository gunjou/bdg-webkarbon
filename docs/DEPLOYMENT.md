# Dokumentasi Deployment — Webkarbon (HRIS Desa Karang Bongkot)

> Dokumen transfer knowledge: konfigurasi VPS, Cloudflare, struktur server, dan alur deploy.
> Terakhir diperbarui: 11 November 2026
>
> ⚠️ Dokumen ini **tidak** berisi password/secret. Semua nilai rahasia hanya ada di server (`.env`, file kredensial tunnel).

---

## Daftar Isi

1. [Ringkasan Arsitektur](#1-ringkasan-arsitektur)
2. [Spesifikasi VPS](#2-spesifikasi-vps)
3. [Struktur Direktori Server](#3-struktur-direktori-server)
4. [Setup Dasar Sistem](#4-setup-dasar-sistem)
5. [PostgreSQL](#5-postgresql)
6. [Aplikasi Backend (Flask)](#6-aplikasi-backend-flask)
7. [Gunicorn (systemd service)](#7-gunicorn-systemd-service)
8. [Nginx (Reverse Proxy)](#8-nginx-reverse-proxy)
9. [Cloudflare Tunnel & DNS](#9-cloudflare-tunnel--dns)
10. [Deploy Otomatis (deploy.sh)](#10-deploy-otomatis-deploysh)
11. [Perintah Operasional Harian](#11-perintah-operasional-harian)
12. [Troubleshooting (Masalah yang Pernah Terjadi)](#12-troubleshooting-masalah-yang-pernah-terjadi)
13. [Baseline Pemakaian Resource](#13-baseline-pemakaian-resource)
14. [Pekerjaan Tersisa (TODO)](#14-pekerjaan-tersisa-todo)

---

## 1. Ringkasan Arsitektur

```
                         ┌──────────────── VPS (Jakarta) ────────────────┐
Pengguna (HP/Browser)    │                                               │
        │                │   cloudflared ──► Nginx :80 ──► Gunicorn :5000│
        ▼                │   (tunnel)        (proxy)      (Flask API)    │
https://bdg.karangbongkot.com                                  │         │
        │                │                                     ▼         │
        ▼                │                            PostgreSQL :5432   │
   Cloudflare ◄──────────┤  (koneksi KELUAR dari VPS,  (localhost only)  │
  (HTTPS/SSL otomatis)   │   tidak perlu port masuk)                     │
                         └───────────────────────────────────────────────┘
```

**Kenapa memakai Cloudflare Tunnel?**
VPS ini memakai **IP publik bersama (NAT)**: `141.11.160.130`. Hanya port tertentu yang diteruskan ke VPS (SSH di `20143`), sehingga port 80/443 **tidak bisa** dipakai langsung. Cloudflare Tunnel mengatasi ini karena:

- VPS membuat koneksi **keluar** ke Cloudflare, sehingga tidak butuh port masuk
- HTTPS/SSL otomatis dari Cloudflare. HTTPS **wajib** karena browser memblokir akses kamera dan GPS tanpa HTTPS
- Hemat biaya IP dedicated (Rp30.000/bulan)

| Komponen           | Teknologi                                                      |
| ------------------ | -------------------------------------------------------------- |
| OS                 | Ubuntu 24.04 LTS                                               |
| Backend            | Flask 3.1 + flask-restx, Python 3.12                           |
| Face recognition   | `face_recognition` + `dlib` 20.0.1                             |
| WSGI server        | Gunicorn 26                                                    |
| Database           | PostgreSQL 16                                                  |
| Web server / proxy | Nginx                                                          |
| Ekspos publik      | Cloudflare Tunnel (`cloudflared`)                              |
| Frontend           | React (belum dibuat), direncanakan untuk `absen.` dan `admin.` |

---

## 2. Spesifikasi VPS

| Item              | Nilai                                                |
| ----------------- | ---------------------------------------------------- |
| Hostname          | `webkarbon-server` (prompt: `webkarbon-server-4468`) |
| Lokasi            | Jakarta, Indonesia                                   |
| vCPU / RAM / Disk | 1 core / 1 GB / 20 GB NVMe                           |
| OS                | Ubuntu 24.04                                         |
| IP                | `141.11.160.130` (**IP bersama / NAT**)              |
| Port SSH          | `20143` (diteruskan ke port 22 di dalam VPS)         |
| Biaya             | Rp25.000/bulan                                       |
| Dibuat            | 11 Nov 2026                                          |
| Berakhir          | **11 Des 2026**. Perpanjang lewat panel              |

**Login SSH:**

```bash
ssh -p 20143 webkarbon@141.11.160.130
```

**Akses darurat:** kalau SSH terkunci, gunakan tombol **Konsol** di panel penyedia.

**Catatan support penyedia:** support tidak 24 jam (WhatsApp/tiket, kira-kira 08.00–22.00 WIB). Karena itu backup harus disimpan di luar VPS.

---

## 3. Struktur Direktori Server

```
/srv/webkarbon/
├── bdg-webkarbon/          # Repo backend (git clone dari GitHub)
│   ├── .env                # Konfigurasi rahasia (chmod 600, TIDAK di-commit)
│   ├── api/                # Kode Flask (package `api`)
│   ├── migrations/         # File SQL migrasi, berurutan 001_, 002_, ...
│   ├── docs/
│   ├── scripts/
│   └── requirements.txt
├── venv/                   # Python virtualenv (Python 3.12)
├── wsgi.py                 # Entry point Gunicorn (di luar repo)
├── deploy.sh               # Script deploy otomatis (di luar repo)
└── deploy.log              # Riwayat deploy

/etc/nginx/sites-available/webkarbon     # Config Nginx
/etc/systemd/system/webkarbon.service    # Service Gunicorn
/etc/cloudflared/config.yml              # Config tunnel
/etc/cloudflared/<TUNNEL_ID>.json        # Kredensial tunnel (RAHASIA)
/etc/sudoers.d/webkarbon-deploy          # Izin restart service tanpa password
/etc/postgresql/16/main/conf.d/tuning.conf
/home/webkarbon/.ssh/github_deploy       # Deploy key GitHub (read-only)
/home/webkarbon/.cloudflared/            # cert.pem & kredensial tunnel asli
```

> `wsgi.py` dan `deploy.sh` sengaja diletakkan **di luar repo**, supaya tidak tertimpa atau berubah saat `git pull`.

---

## 4. Setup Dasar Sistem

### 4.1 Update & zona waktu

Zona waktu WITA penting karena aplikasi menghitung jam masuk dan keterlambatan.

```bash
apt update && apt upgrade -y
timedatectl set-timezone Asia/Makassar
```

### 4.2 Swap 2 GB

Swap ini sangat penting untuk RAM 1 GB, terutama saat compile `dlib`.

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swap.conf
sysctl -p /etc/sysctl.d/99-swap.conf
```

`swappiness=10` membuat swap hanya dipakai saat RAM hampir penuh.

### 4.3 User aplikasi

Aplikasi berjalan sebagai user `webkarbon`, bukan `root`.

```bash
adduser webkarbon
usermod -aG sudo webkarbon
```

### 4.4 Firewall (UFW)

Hanya SSH yang dibuka. Port 80/443 **tidak perlu** dibuka karena trafik web masuk lewat Cloudflare Tunnel.

```bash
ufw allow OpenSSH
ufw enable
```

### 4.5 Paket sistem

```bash
apt install -y python3-venv python3-dev python3-pip build-essential libpq-dev \
  postgresql nginx git curl
# Khusus dlib / face_recognition:
apt install -y cmake libopenblas-dev liblapack-dev libjpeg-dev tmux
```

---

## 5. PostgreSQL

### 5.1 Tuning hemat RAM

File `/etc/postgresql/16/main/conf.d/tuning.conf`:

```ini
shared_buffers = 128MB
effective_cache_size = 384MB
work_mem = 4MB
maintenance_work_mem = 32MB
max_connections = 20
```

Lalu jalankan `sudo systemctl restart postgresql`.

### 5.2 Database & user

| Item     | Nilai                                             |
| -------- | ------------------------------------------------- |
| Database | `webkarbon`                                       |
| User     | `karbon` (owner database)                         |
| Host     | `localhost`, tidak dibuka ke internet             |
| Password | Acak, dibuat di server, hanya tersimpan di `.env` |

Kalau migrasi gagal dengan `permission denied for schema public`:

```bash
sudo -u postgres psql -c "ALTER DATABASE webkarbon OWNER TO karbon;"
sudo -u postgres psql -d webkarbon -c "ALTER SCHEMA public OWNER TO karbon;"
```

### 5.3 Tabel pencatat migrasi

Tabel `schema_migrations` dipakai `deploy.sh` untuk mengetahui migrasi mana yang sudah dijalankan:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
  filename   TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Migrasi `001_init.sql` dan `002_kode_pemulihan_dan_seed_roles.sql` dijalankan manual saat setup awal, lalu ditandai sebagai sudah dijalankan.

---

## 6. Aplikasi Backend (Flask)

### 6.1 Koneksi ke GitHub (deploy key)

```bash
ssh-keygen -t ed25519 -C "webkarbon-server" -f ~/.ssh/github_deploy -N ""
cat >> ~/.ssh/config << 'EOF'
Host github.com
  IdentityFile ~/.ssh/github_deploy
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```

Public key (`~/.ssh/github_deploy.pub`) didaftarkan di GitHub: **Repo → Settings → Deploy keys**, **tanpa** write access.

### 6.2 Clone & virtualenv

```bash
cd /srv/webkarbon
git clone git@github.com:<USERNAME>/bdg-webkarbon.git
python3 -m venv /srv/webkarbon/venv
source /srv/webkarbon/venv/bin/activate
pip install --upgrade pip wheel
pip install "setuptools<81"
pip install dlib==20.0.1          # compile 20–40 menit, jalankan di dalam tmux
pip install -r bdg-webkarbon/requirements.txt
```

> **Penting:** `setuptools` harus `<81`. Paket `face_recognition_models` masih memakai `pkg_resources`, yang sudah dihapus di setuptools versi baru. Lihat bagian [Troubleshooting](#12-troubleshooting-masalah-yang-pernah-terjadi).

Verifikasi:

```bash
python -c "import face_recognition, dlib; print('OK', dlib.__version__)"
```

### 6.3 File `.env`

Lokasi: `/srv/webkarbon/bdg-webkarbon/.env` (permission `600`, tercantum di `.gitignore`).

| Variabel              | Nilai / Keterangan                                 |
| --------------------- | -------------------------------------------------- |
| `DB_HOST`             | `localhost`                                        |
| `DB_PORT`             | `5432`                                             |
| `DB_NAME`             | `webkarbon`                                        |
| `DB_USER`             | `karbon`                                           |
| `DB_PASSWORD`         | 🔒 acak, dibuat dengan `secrets.token_urlsafe(24)` |
| `JWT_SECRET_KEY`      | 🔒 acak, dibuat dengan `secrets.token_urlsafe(48)` |
| `JWT_ACCESS_EXPIRES`  | `480`                                              |
| `JWT_REFRESH_EXPIRES` | `7`                                                |

Cara membuat ulang secret (misalnya kalau bocor):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

> Mengganti `JWT_SECRET_KEY` membuat semua sesi login tidak berlaku, dan semua pengguna harus login ulang.
> Mengganti `DB_PASSWORD` juga harus diikuti dengan `ALTER USER karbon WITH PASSWORD '...'` di PostgreSQL.

### 6.4 `wsgi.py`

Lokasi: `/srv/webkarbon/wsgi.py`

```python
import sys
sys.path.insert(0, "/srv/webkarbon/bdg-webkarbon")

from dotenv import load_dotenv
load_dotenv("/srv/webkarbon/bdg-webkarbon/.env")

import api
app = api.create_app() if hasattr(api, "create_app") else api.app
```

---

## 7. Gunicorn (systemd service)

File `/etc/systemd/system/webkarbon.service`:

```ini
[Unit]
Description=Webkarbon API (Flask + Gunicorn)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
User=webkarbon
Group=webkarbon
WorkingDirectory=/srv/webkarbon/bdg-webkarbon
EnvironmentFile=/srv/webkarbon/bdg-webkarbon/.env
Environment=PYTHONWARNINGS=ignore::UserWarning
ExecStart=/srv/webkarbon/venv/bin/gunicorn \
    --pythonpath /srv/webkarbon \
    --bind 127.0.0.1:5000 \
    --workers 2 --preload \
    --timeout 60 \
    --max-requests 500 --max-requests-jitter 50 \
    --access-logfile - --error-logfile - \
    wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

| Opsi                    | Alasan                                                                          |
| ----------------------- | ------------------------------------------------------------------------------- |
| `--bind 127.0.0.1:5000` | Hanya bisa diakses dari dalam server (lewat Nginx)                              |
| `--workers 2 --preload` | 2 proses paralel; model wajah dimuat **sekali** lalu dibagi, sehingga hemat RAM |
| `--timeout 60`          | Proses pencocokan wajah di 1 vCPU bisa butuh beberapa detik                     |
| `--max-requests 500`    | Worker diganti berkala untuk mencegah memori membengkak                         |
| `PYTHONWARNINGS`        | Menyembunyikan peringatan `pkg_resources` yang tidak berbahaya                  |
| `Restart=always`        | Otomatis menyala lagi kalau crash                                               |

> Karena memakai `--preload`, perubahan kode **wajib** diikuti `restart`, bukan `reload`.

Aktivasi:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now webkarbon
```

Health check (respons ini **normal** dan menandakan API hidup):

```bash
curl -s http://127.0.0.1:5000/auth/me
# {"code":"TOKEN_MISSING","errors":null,"message":"Token tidak ditemukan","success":false}
```

---

## 8. Nginx (Reverse Proxy)

File `/etc/nginx/sites-available/webkarbon` (di-symlink ke `sites-enabled`, dan `default` dihapus):

```nginx
server {
    listen 80;
    server_name bdg.karangbongkot.com;
    client_max_body_size 5M;          # batas upload foto selfie

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $http_cf_connecting_ip;        # IP asli dari Cloudflare
        proxy_set_header X-Forwarded-For $http_cf_connecting_ip;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 60s;
    }
}
```

Tes reverse proxy dari dalam server:

```bash
sudo nginx -t && sudo systemctl reload nginx
curl -s -H "Host: bdg.karangbongkot.com" http://127.0.0.1/auth/me
```

### Template frontend React (saat sudah siap)

Tambahkan blok berikut, buat folder `/srv/webkarbon/www/absen` dan `/srv/webkarbon/www/admin`, lalu tambahkan juga ingress-nya di tunnel (lihat bagian 9.2):

```nginx
server {
    listen 80;
    server_name absen.karangbongkot.com;
    root /srv/webkarbon/www/absen;
    index index.html;
    location / { try_files $uri $uri/ /index.html; }   # agar routing React tidak 404
}
```

---

## 9. Cloudflare Tunnel & DNS

### 9.1 Pembuatan tunnel

```bash
cloudflared tunnel login                 # buka URL di browser, pilih karangbongkot.com
cloudflared tunnel create webkarbon
cloudflared tunnel route dns --overwrite-dns webkarbon bdg.karangbongkot.com
```

| Item        | Nilai                                                        |
| ----------- | ------------------------------------------------------------ |
| Nama tunnel | `webkarbon`                                                  |
| Tunnel ID   | `7281ddcd-0900-4d51-8ece-f744422595ef`                       |
| Kredensial  | `/etc/cloudflared/7281ddcd-....json` 🔒 **jangan dibagikan** |

> Opsi `--overwrite-dns` dipakai untuk menimpa A record lama yang masih mengarah ke VPS lama.

### 9.2 Konfigurasi tunnel

File `/etc/cloudflared/config.yml`:

```yaml
tunnel: 7281ddcd-0900-4d51-8ece-f744422595ef
credentials-file: /etc/cloudflared/7281ddcd-0900-4d51-8ece-f744422595ef.json

ingress:
  - hostname: bdg.karangbongkot.com
    service: http://localhost:80
  # Tambahkan saat frontend siap:
  # - hostname: absen.karangbongkot.com
  #   service: http://localhost:80
  # - hostname: admin.karangbongkot.com
  #   service: http://localhost:80
  - service: http_status:404
```

Dijalankan sebagai service:

```bash
sudo cloudflared service install
sudo systemctl restart cloudflared      # setiap kali config.yml diubah
```

### 9.3 Status DNS `karangbongkot.com` (Cloudflare)

| Record                     | Tipe      | Tujuan                         | Proxy        | Keterangan                                                     |
| -------------------------- | --------- | ------------------------------ | ------------ | -------------------------------------------------------------- |
| `bdg`                      | CNAME     | `<TUNNEL_ID>.cfargotunnel.com` | Proxied      | **API backend (VPS baru)**                                     |
| `absen`                    | —         | —                              | —            | Rencana frontend pegawai. Cek statusnya di dashboard           |
| `admin`                    | —         | —                              | —            | Rencana frontend admin. Cek statusnya di dashboard             |
| `karangbongkot.com`, `www` | A / CNAME | `72.60.74.195`                 | Proxied      | Masih di VPS lama                                              |
| `mail`                     | A         | `163.223.227.8`                | **DNS only** | ⚠️ **Wajib DNS only**, kalau Proxied email tidak bisa diterima |
| `webmail`                  | A         | `163.223.227.8`                | Proxied      | Hanya halaman web, boleh Proxied                               |
| MX, SPF, DKIM, DMARC       | MX/TXT    | —                              | DNS only     | Konfigurasi email                                              |

> **Jangan arahkan subdomain ke IP `141.11.160.130`.** IP itu dipakai bersama, sehingga port 80/443-nya bukan milik VPS ini. Semua subdomain untuk VPS baru harus lewat tunnel (CNAME).

---

## 10. Deploy Otomatis (`deploy.sh`)

### 10.1 Persiapan (sekali saja)

Izinkan user `webkarbon` me-restart service tanpa password. Izin ini **hanya** untuk perintah tersebut:

```bash
echo 'webkarbon ALL=(root) NOPASSWD: /usr/bin/systemctl restart webkarbon' | sudo tee /etc/sudoers.d/webkarbon-deploy
sudo chmod 440 /etc/sudoers.d/webkarbon-deploy
sudo visudo -c
```

### 10.2 Alur kerja script

1. Tolak deploy kalau ada file yang diedit manual di server
2. `git fetch`, lalu fast-forward ke commit terbaru
3. `pip install`, **hanya** kalau `requirements.txt` berubah
4. Jalankan migrasi SQL yang **belum tercatat** di `schema_migrations` (satu file = satu transaksi)
5. Restart service, lalu cek API selama maksimal 30 detik
6. Kalau ada langkah yang gagal, **rollback otomatis** ke commit sebelumnya

### 10.3 Isi `/srv/webkarbon/deploy.sh`

```bash
#!/usr/bin/env bash
# Deploy otomatis backend Webkarbon
# Pakai: ./deploy.sh          (deploy jika ada commit baru)
#        ./deploy.sh --force  (paksa restart walau tidak ada commit baru)
set -Eeuo pipefail

APP_DIR=/srv/webkarbon/bdg-webkarbon
VENV=/srv/webkarbon/venv
SERVICE=webkarbon
HEALTH_URL=http://127.0.0.1:5000/auth/me
LOG_FILE=/srv/webkarbon/deploy.log

exec > >(tee -a "$LOG_FILE") 2>&1

exec 9>/tmp/webkarbon-deploy.lock
flock -n 9 || { echo "Deploy lain sedang berjalan, batal."; exit 1; }

log() { echo "[$(date '+%F %T')] $*"; }

cd "$APP_DIR"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  log "ERROR: ada perubahan lokal di server. Commit dari laptop, jangan edit di server:"
  git status --short --untracked-files=no
  exit 1
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
OLD=$(git rev-parse HEAD)
git fetch --quiet origin "$BRANCH"
NEW=$(git rev-parse "origin/$BRANCH")

if [[ "$OLD" == "$NEW" && "${1:-}" != "--force" ]]; then
  log "Sudah versi terbaru (${OLD:0:7}). Tidak ada yang di-deploy."
  exit 0
fi

log "===== DEPLOY $BRANCH: ${OLD:0:7} -> ${NEW:0:7} ====="
git --no-pager log --oneline "$OLD..$NEW" || true

DEPS_CHANGED=0
rollback() {
  trap - ERR
  log "!!! Deploy GAGAL — rollback ke ${OLD:0:7}"
  git reset --hard --quiet "$OLD"
  if [[ "$DEPS_CHANGED" == 1 ]]; then
    "$VENV/bin/pip" install -q -r requirements.txt || true
  fi
  sudo systemctl restart "$SERVICE"
  log "Rollback selesai. Catatan: migrasi database yang sudah jalan TIDAK ikut di-rollback."
  exit 1
}
trap rollback ERR

git merge --ff-only --quiet "origin/$BRANCH"
CHANGED=$(git diff --name-only "$OLD" "$NEW")

if grep -qx "requirements.txt" <<< "$CHANGED"; then
  DEPS_CHANGED=1
  log "requirements.txt berubah — install dependensi..."
  "$VENV/bin/pip" install -q -r requirements.txt
fi

set -a; source "$APP_DIR/.env"; set +a
export PGPASSWORD="$DB_PASSWORD"
PSQL=(psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -q)

"${PSQL[@]}" -c "CREATE TABLE IF NOT EXISTS schema_migrations (
  filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());"

for f in migrations/*.sql; do
  name=$(basename "$f")
  if [[ -z "$("${PSQL[@]}" -tAc "SELECT 1 FROM schema_migrations WHERE filename = '$name'")" ]]; then
    log "Menjalankan migrasi: $name"
    "${PSQL[@]}" --single-transaction -f "$f" \
      -c "INSERT INTO schema_migrations (filename) VALUES ('$name');"
  fi
done
unset PGPASSWORD

log "Restart service $SERVICE..."
sudo systemctl restart "$SERVICE"

for i in $(seq 1 30); do
  if curl -s --max-time 3 "$HEALTH_URL" | grep -q '"success"'; then
    trap - ERR
    log "✅ Deploy BERHASIL — versi ${NEW:0:7} sudah aktif (${i} detik)."
    free -h | awk 'NR<=2'
    exit 0
  fi
  sleep 1
done

log "API tidak merespons setelah 30 detik."
rollback
```

### 10.4 Cara pakai

Dari laptop, setelah `git push`:

```bash
ssh -p 20143 webkarbon@141.11.160.130 /srv/webkarbon/deploy.sh
```

Alias opsional di laptop (`~/.zshrc` / `~/.bashrc`):

```bash
alias deploy-karbon='ssh -p 20143 webkarbon@141.11.160.130 /srv/webkarbon/deploy.sh'
```

### 10.5 Aturan wajib

| ✅ Lakukan                                                | ❌ Jangan                                                                 |
| --------------------------------------------------------- | ------------------------------------------------------------------------- |
| Beri nomor urut migrasi baru: `003_...sql`, `004_...sql`  | Mengedit file migrasi yang sudah pernah dijalankan                        |
| Ubah kode di laptop, lalu commit, push, dan deploy        | Mengedit kode langsung di server (deploy akan ditolak)                    |
| Biarkan script yang membungkus migrasi dalam transaksi    | Menulis `BEGIN;` / `COMMIT;` di dalam file migrasi                        |
| Untuk perubahan skema yang berisiko, backup database dulu | Mengandalkan rollback untuk database (migrasi **tidak** ikut di-rollback) |

---

## 11. Perintah Operasional Harian

```bash
# Status semua service
systemctl is-active webkarbon nginx postgresql cloudflared

# Log aplikasi (live)
sudo journalctl -u webkarbon -f

# Log tunnel
sudo journalctl -u cloudflared -f

# Restart aplikasi (setelah ubah .env)
sudo systemctl restart webkarbon

# Pemakaian RAM & disk
free -h
df -h /
systemctl status webkarbon --no-pager | grep Memory

# Riwayat deploy
tail -n 50 /srv/webkarbon/deploy.log

# Masuk ke database
cd /srv/webkarbon/bdg-webkarbon && set -a && source .env && set +a
PGPASSWORD="$DB_PASSWORD" psql -h localhost -U "$DB_USER" -d "$DB_NAME"

# Tes API dari luar
curl -s https://bdg.karangbongkot.com/auth/me
```

---

## 12. Troubleshooting (Masalah yang Pernah Terjadi)

| Gejala                                                               | Penyebab                                        | Solusi                                                                                      |
| -------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `Please install face_recognition_models ...` padahal sudah terinstal | `setuptools` ≥ 81 menghapus `pkg_resources`     | `pip install "setuptools<81"`                                                               |
| Peringatan `pkg_resources is deprecated` di log                      | Library lama, tidak berbahaya                   | Diabaikan lewat `PYTHONWARNINGS` di service                                                 |
| `ModuleNotFoundError: No module named 'api'`                         | Path di `wsgi.py` tidak sesuai nama folder repo | Pastikan path di `wsgi.py` = `/srv/webkarbon/bdg-webkarbon`                                 |
| `cloudflared tunnel route dns` → `record already exists`             | Subdomain masih punya A record lama             | Tambahkan `--overwrite-dns`                                                                 |
| `deploy.sh` → `ada perubahan lokal di server`                        | Ada file repo yang diedit di server             | `git diff` untuk melihat perubahan, pindahkan ke repo laptop, lalu `git checkout -- <file>` |
| Hanya beda file mode / CRLF di `git status`                          | Perbedaan permission atau akhir baris           | `git config core.fileMode false`, lalu `git checkout -- <file>`                             |
| `permission denied for schema public`                                | Database bukan milik user `karbon`              | Lihat bagian 5.2                                                                            |
| `502 Bad Gateway` di `bdg.`                                          | Gunicorn mati atau belum jalan                  | `systemctl status webkarbon`, cek `journalctl -u webkarbon`                                 |
| `pip install dlib` → `Killed`                                        | RAM dan swap habis saat compile                 | Pastikan swap aktif (`free -h`), jalankan ulang di dalam `tmux`                             |
| Kamera/GPS tidak jalan di browser                                    | Halaman tidak memakai HTTPS                     | Selalu akses lewat `https://` (tunnel Cloudflare)                                           |
| Email ke `@karangbongkot.com` tidak masuk                            | Record `mail` berstatus Proxied                 | Ubah ke **DNS only**                                                                        |

---

## 13. Baseline Pemakaian Resource

| Kondisi                                   | RAM terpakai                 | RAM tersedia |
| ----------------------------------------- | ---------------------------- | ------------ |
| Ubuntu kosong                             | ~0,4 GB                      | —            |
| + PostgreSQL + Nginx                      | 357 MB                       | 603 MB       |
| + Gunicorn 2 worker (model wajah termuat) | 458 MB (service: **192 MB**) | **503 MB**   |

- Saat memproses foto selfie, pemakaian naik sementara sekitar 50–100 MB per request.
- Disk: sekitar 14 GB tersisa setelah setup. Foto absensi sekitar 50 KB per foto, kira-kira 750 MB/tahun untuk 30 pegawai.
- **Rekomendasi:** upgrade ke RAM 2 GB sebelum fitur **persuratan** (generate PDF) diaktifkan. Gunakan `WeasyPrint` atau `docxtpl`, dan hindari LibreOffice/Chromium yang berat.

---

## 14. Pekerjaan Tersisa (TODO)

**Prioritas tinggi**

- [ ] Buat akun **SUPER_ADMIN** pertama, misalnya lewat migrasi `003_seed_super_admin.sql` atau skrip di `scripts/`
- [ ] Tambahkan `setuptools<81` ke `requirements.txt`
- [ ] **Backup database otomatis ke luar VPS** (misalnya `pg_dump` via cron ke Google Drive/object storage)
- [ ] **Tutup port 5432 di VPS lama** (`72.60.74.195`), karena PostgreSQL di sana sempat terbuka ke internet dengan password lama yang sudah bocor
- [ ] Pastikan lokasi penyimpanan foto (`api/core/storage.py`) berada di path yang benar dan bisa ditulis oleh user `webkarbon`
- [ ] Perpanjang VPS sebelum **11 Des 2026**

**Prioritas sedang**

- [ ] Batasi CORS hanya untuk `https://absen.karangbongkot.com` dan `https://admin.karangbongkot.com`
- [ ] Pertimbangkan menonaktifkan Swagger UI di production, atau melindunginya
- [ ] Buat frontend React (`absen` & `admin`): build di laptop, upload ke `/srv/webkarbon/www/...`, lalu tambahkan blok Nginx dan ingress tunnel
- [ ] Pindahkan `karangbongkot.com` / `www` dari VPS lama kalau VPS lama akan dimatikan

**Ke depan**

- [ ] Upgrade RAM ke 2 GB sebelum modul persuratan
- [ ] Opsional: otomatisasi deploy lewat GitHub Actions
