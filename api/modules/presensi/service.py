# api/modules/presensi/service.py
"""
Ketentuan presensi pegawai (semua waktu = jam server WITA, bukan jam HP):

1. Akun harus tertaut ke pegawai aktif yang sudah punya foto wajah (embedding) dan jadwal kerja aktif.
2. Jadwal  : bukan hari libur aktif, dan hari ini hari kerja di jadwal_harian.
   - masuk  : dibuka ABSEN_MASUK_BUKA_MENIT sebelum jam masuk, ditutup saat jam pulang.
              Lewat jam masuk + toleransi -> 'terlambat', terlambat_menit dihitung dari jam masuk.
   - pulang : boleh jika sudah absen masuk, atau (lupa masuk) jam pulang sudah lewat. Sampai akhir hari.
              Sebelum jam pulang -> 'pulang_cepat'.
   - Masing-masing hanya 1x per hari.
3. GPS     : akurasi <= GPS_MAX_AKURASI_METER, dan di dalam radius lokasi kantor aktif TERDEKAT
             (pegawai tidak diikat ke satu lokasi; semua lokasi aktif sah).
4. Wajah   : (foto disimpan dikompres <= 20 KB setelah dicocokkan) foto berisi tepat 1 wajah dan cocok dgn foto enrollment (jarak <= FACE_MATCH_THRESHOLD).
Urutan cek: akun -> jadwal -> GPS -> wajah (yang murah dulu). Setiap kegagalan dicatat ke absensi_gagal.

Perizinan (pegawai, milik sendiri):
- izin    : id_jenis_izin aktif wajib; rentang maks MAX_IZIN_HARI; tidak boleh beririsan dgn izin lain
            yang diajukan/disetujui; lampiran wajib jika jenis_izin.butuh_lampiran = 1.
- koreksi : 1 tanggal, hari ini s/d MAX_KOREKSI_HARI ke belakang; jenis_absen + jam_koreksi wajib;
            absen jenis tsb belum tercatat; tidak ada koreksi aktif yang sama.
- lampiran: jpg/png (dikompres <= LAMPIRAN_MAX_BYTES) atau pdf (apa adanya, batas MAX_UPLOAD_MB).
- Tidak ada ubah; batal hanya saat status 'diajukan'. Review (setuju/tolak) bukan di modul ini.
- hari_ini.izin = izin diajukan/disetujui yang mencakup hari ini (frontend memblokir presensi).
"""
import os
from datetime import date, time, timedelta

from PIL import UnidentifiedImageError

from api.core import storage
from api.modules.master.jadwal_kerja.service import HARI
from api.modules.master.jenis_izin import service as jenis_izin_service
from api.shared.exceptions import AppError, ForbiddenError, NotFoundError, ValidationError
from api.utils.datetime import get_wita
from api.utils.face import FaceError, face_distance, process_face_photo
from api.utils.geo import haversine_m
from api.utils.image import compress_jpeg
from . import query

# default; bisa ditimpa lewat tabel settings (key sama)
DEFAULT_SETTINGS = {
    "ABSEN_MASUK_BUKA_MENIT": 60,
    "GPS_MAX_AKURASI_METER": 50,
    "FACE_MATCH_THRESHOLD": 0.5,
}
MAX_RANGE_HARI = 62
FOTO_MAX_BYTES = 20 * 1024  # foto presensi disimpan <= 20 KB
LAMPIRAN_MAX_BYTES = 200 * 1024  # lampiran gambar (surat dokter dsb.) harus tetap terbaca
MAX_IZIN_HARI = 30
MAX_KOREKSI_HARI = 7


class PresensiError(AppError):
    def __init__(self, code, message):
        super().__init__(message=message, code=code, status_code=422)


def _settings():
    return {**DEFAULT_SETTINGS, **query.get_settings(DEFAULT_SETTINGS)}


def _fail(ctx, stage, code, message, **extra):
    """Catat ke absensi_gagal (transaksi sendiri, tetap tersimpan) lalu raise."""
    query.insert_gagal({"id_pegawai": ctx["id_pegawai"], "source": "server", "stage": stage,
                        "error_code": code, "error_message": message, **extra})
    raise PresensiError(code, message)


def _context(id_user, tanggal):
    ctx = query.get_context(id_user, tanggal)
    if not ctx:
        raise ForbiddenError("Akun tidak tertaut ke data pegawai")
    if ctx["is_active"] != 1:
        raise ForbiddenError("Pegawai tidak aktif")
    return ctx


def _today_rows(id_pegawai, tanggal):
    return {r["jenis"]: r for r in query.get_range(id_pegawai, tanggal, tanggal)}


def _jadwal_hari_ini(ctx, now):
    """Kembalikan ((jam_masuk_dt, jam_pulang_dt), None, None) atau (None, kode, pesan)."""
    if ctx["libur"]:
        return None, "HOLIDAY", f"Hari ini libur: {ctx['libur']}"
    if not ctx["jadwal_harian"]:
        return None, "NO_SCHEDULE", "Pegawai belum punya jadwal kerja"
    hari = ctx["jadwal_harian"].get(HARI[now.weekday()])
    if not hari:
        return None, "NOT_WORKDAY", "Hari ini bukan hari kerja"

    def at(hhmm):
        h, m = map(int, hhmm.split(":"))
        return now.replace(hour=h, minute=m, second=0, microsecond=0)

    return (at(hari["masuk"]), at(hari["pulang"])), None, None


def _cek_jadwal(ctx, jenis, now, done, cfg):
    """Kembalikan dict jam_jadwal, terlambat_menit, status. Gagal -> _fail stage SCHEDULE."""
    jadwal, code, msg = _jadwal_hari_ini(ctx, now)
    if not jadwal:
        _fail(ctx, "SCHEDULE", code, msg, jenis=jenis)
    masuk, pulang = jadwal
    if jenis in done:
        _fail(ctx, "SCHEDULE", "ALREADY_CHECKED", f"Sudah absen {jenis} hari ini", jenis=jenis)

    if jenis == "masuk":
        buka = masuk - timedelta(minutes=int(cfg["ABSEN_MASUK_BUKA_MENIT"]))
        if now < buka:
            _fail(ctx, "SCHEDULE", "OUTSIDE_TIME_WINDOW", f"Absen masuk dibuka pukul {buka:%H:%M}", jenis=jenis)
        if now >= pulang:
            _fail(ctx, "SCHEDULE", "OUTSIDE_TIME_WINDOW",
                  f"Absen masuk ditutup pukul {pulang:%H:%M}, ajukan koreksi absen", jenis=jenis)
        telat = int((now - masuk).total_seconds() // 60)
        if telat > int(ctx["toleransi_terlambat_menit"] or 0):
            return {"jam_jadwal": masuk.time(), "terlambat_menit": telat, "status": "terlambat"}
        return {"jam_jadwal": masuk.time(), "terlambat_menit": 0, "status": "tepat_waktu"}

    # pulang
    if "masuk" not in done and now < pulang:
        _fail(ctx, "SCHEDULE", "NOT_CHECKED_IN", "Belum absen masuk", jenis=jenis)
    status = "pulang_cepat" if now < pulang else "tepat_waktu"
    return {"jam_jadwal": pulang.time(), "terlambat_menit": 0, "status": status}


def _cek_lokasi(ctx, jenis, lat, lon, akurasi, cfg):
    gps = {"jenis": jenis, "latitude": lat, "longitude": lon, "akurasi_gps": akurasi}
    if akurasi is None or akurasi < 0 or akurasi > float(cfg["GPS_MAX_AKURASI_METER"]):
        _fail(ctx, "GPS", "GPS_LOW_ACCURACY",
              f"Akurasi GPS kurang baik (maks {cfg['GPS_MAX_AKURASI_METER']} m), coba di area terbuka", **gps)
    lokasi = query.get_lokasi_aktif()
    if not lokasi:
        _fail(ctx, "LOCATION", "NO_OFFICE_LOCATION", "Lokasi kantor belum diatur", **gps)
    jarak, lk = min(((haversine_m(lat, lon, lk["latitude"], lk["longitude"]), lk) for lk in lokasi),
                    key=lambda x: x[0])
    jarak = round(jarak, 2)
    if jarak > lk["radius_meter"]:
        _fail(ctx, "LOCATION", "OUTSIDE_RADIUS",
              f"Di luar area {lk['name']} ({jarak:.0f} m, maks {lk['radius_meter']} m)",
              id_lokasi_kantor=lk["id_lokasi_kantor"], jarak_meter=jarak, **gps)
    return lk, jarak


def _cek_wajah(ctx, jenis, foto, gps, cfg):
    """Kembalikan (jpeg, skor). Foto yang tidak cocok disimpan untuk audit admin."""
    try:
        jpeg, embedding = process_face_photo(foto)
    except FaceError as e:
        _fail(ctx, "FACE", "FACE_NOT_DETECTED", str(e), jenis=jenis, **gps)
    dist = face_distance(ctx["embedding"], embedding)
    skor = round(max(0.0, 1 - dist), 4)
    if dist > float(cfg["FACE_MATCH_THRESHOLD"]):
        path = storage.save_file(compress_jpeg(jpeg, FOTO_MAX_BYTES), f"absensi_gagal/{get_wita():%Y-%m}", "jpg")
        _fail(ctx, "FACE", "FACE_NOT_MATCH", "Wajah tidak cocok", jenis=jenis, skor_wajah=skor,
              photo_path=path, detail={"distance": round(dist, 4)}, **gps)
    return jpeg, skor


def absen(id_user, jenis, lat, lon, akurasi, foto):
    now = get_wita()
    tanggal = now.date()
    ctx = _context(id_user, tanggal)
    if not ctx["embedding"]:
        _fail(ctx, "FACE", "FACE_NOT_ENROLLED", "Foto wajah belum didaftarkan, hubungi admin", jenis=jenis)
    cfg = _settings()

    done = _today_rows(ctx["id_pegawai"], tanggal)
    jadwal = _cek_jadwal(ctx, jenis, now, done, cfg)
    lk, jarak = _cek_lokasi(ctx, jenis, lat, lon, akurasi, cfg)
    gps = {"latitude": lat, "longitude": lon, "akurasi_gps": akurasi,
           "id_lokasi_kantor": lk["id_lokasi_kantor"], "jarak_meter": jarak}
    jpeg, skor = _cek_wajah(ctx, jenis, foto, gps, cfg)

    path = storage.save_file(compress_jpeg(jpeg, FOTO_MAX_BYTES), f"absensi/{now:%Y-%m}", "jpg")
    data = {"id_pegawai": ctx["id_pegawai"], "tanggal": tanggal, "jenis": jenis, "waktu_absen": now,
            "skor_wajah": skor, "photo_path": path, "created_by": id_user, **gps, **jadwal}
    try:
        id_absensi = query.insert(data)
    except Exception:
        storage.delete_file(path)
        raise
    if id_absensi is None:  # double submit bersamaan
        storage.delete_file(path)
        raise PresensiError("ALREADY_CHECKED", f"Sudah absen {jenis} hari ini")
    return _public(query.get_by_id(id_absensi))


def hari_ini(id_user):
    """Info layar absen: jadwal hari ini & yang sudah dilakukan."""
    now = get_wita()
    ctx = _context(id_user, now.date())
    cfg = _settings()
    done = _today_rows(ctx["id_pegawai"], now.date())
    jadwal, code, msg = _jadwal_hari_ini(ctx, now)
    return {
        "tanggal": now.date(),
        "waktu_server": now,
        "pegawai": {"id_pegawai": ctx["id_pegawai"], "full_name": ctx["full_name"],
                    "face_enrolled": bool(ctx["embedding"])},
        "hari_kerja": jadwal is not None,
        "kode": code,
        "keterangan": msg,
        "jadwal": jadwal and {
            "nama": ctx["jadwal_kerja_name"],
            "masuk": jadwal[0].time(), "pulang": jadwal[1].time(),
            "masuk_dibuka": (jadwal[0] - timedelta(minutes=int(cfg["ABSEN_MASUK_BUKA_MENIT"]))).time(),
            "toleransi_terlambat_menit": ctx["toleransi_terlambat_menit"],
        },
        "masuk": done.get("masuk"),
        "pulang": done.get("pulang"),
        "gps_max_akurasi_meter": cfg["GPS_MAX_AKURASI_METER"],
        "izin": query.get_izin_aktif(ctx["id_pegawai"], now.date()),
    }


def lapor_gagal(id_user, data):
    ctx = _context(id_user, get_wita().date())
    detail = data.get("detail")
    if detail is not None and not isinstance(detail, dict):
        raise ValidationError("detail harus object", {"detail": "object"})
    query.insert_gagal({**data, "id_pegawai": ctx["id_pegawai"], "source": "client",
                        "error_message": (data.get("error_message") or "")[:500] or None})


def _range(args):
    """Default = awal bulan berjalan s/d hari ini."""
    today = get_wita().date()
    try:
        mulai = date.fromisoformat(args["tanggal_mulai"]) if args.get("tanggal_mulai") else today.replace(day=1)
        selesai = date.fromisoformat(args["tanggal_selesai"]) if args.get("tanggal_selesai") else today
    except ValueError:
        raise ValidationError("Format tanggal YYYY-MM-DD")
    if selesai < mulai:
        raise ValidationError("tanggal_selesai harus >= tanggal_mulai")
    if (selesai - mulai).days >= MAX_RANGE_HARI:
        raise ValidationError(f"Rentang maksimal {MAX_RANGE_HARI} hari")
    return mulai, selesai


def riwayat(id_user, args):
    ctx = _context(id_user, get_wita().date())
    return query.get_range(ctx["id_pegawai"], *_range(args))


def _public(row):
    return {k: v for k, v in row.items() if k != "photo_path"}


def foto_path(id_user, id_absensi):
    """Hanya milik sendiri; milik orang lain dijawab 404 agar id tidak bisa ditebak."""
    ctx = _context(id_user, get_wita().date())
    row = query.get_by_id(id_absensi)
    if not row or row["id_pegawai"] != ctx["id_pegawai"]:
        raise NotFoundError("Absensi tidak ditemukan")
    full = storage.full_path(row["photo_path"])
    if not full or not os.path.exists(full):
        raise NotFoundError("Foto tidak ditemukan")
    return full


# ======================================================
# PERIZINAN
# ======================================================
def list_jenis_izin():
    return jenis_izin_service.list_all()


def _tanggal(value, field):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError("Format tanggal YYYY-MM-DD", {field: "YYYY-MM-DD"})


def _lampiran(raw):
    """Kembalikan (bytes, ext) atau (None, None). Gambar dikompres, PDF apa adanya."""
    if not raw:
        return None, None
    if raw[:5] == b"%PDF-":
        return raw, "pdf"
    try:
        return compress_jpeg(raw, LAMPIRAN_MAX_BYTES), "jpg"
    except (UnidentifiedImageError, OSError):
        raise ValidationError("Lampiran harus jpg, png, atau pdf", {"lampiran": "jpg/png/pdf"})


def _clean_izin(ctx, data, today):
    try:
        jenis = jenis_izin_service.get(data.get("id_jenis_izin") or 0)
    except NotFoundError:
        jenis = None
    if not jenis or jenis["is_active"] != 1:
        raise ValidationError("Jenis izin tidak valid", {"id_jenis_izin": "required"})
    mulai = _tanggal(data.get("tanggal_mulai"), "tanggal_mulai")
    selesai = _tanggal(data.get("tanggal_selesai") or data.get("tanggal_mulai"), "tanggal_selesai")
    if selesai < mulai:
        raise ValidationError("tanggal_selesai harus >= tanggal_mulai", {"tanggal_selesai": ">= tanggal_mulai"})
    if (selesai - mulai).days >= MAX_IZIN_HARI:
        raise ValidationError(f"Rentang izin maksimal {MAX_IZIN_HARI} hari")
    if query.count_izin_bentrok(ctx["id_pegawai"], mulai, selesai):
        raise ValidationError("Sudah ada izin lain pada rentang tanggal tersebut")
    return {"id_jenis_izin": jenis["id_jenis_izin"], "jenis_absen": None, "jam_koreksi": None,
            "tanggal_mulai": mulai, "tanggal_selesai": selesai}, jenis["butuh_lampiran"] == 1


def _clean_koreksi(ctx, data, today):
    tanggal = _tanggal(data.get("tanggal_mulai"), "tanggal_mulai")
    if tanggal > today or (today - tanggal).days > MAX_KOREKSI_HARI:
        raise ValidationError(f"Koreksi hanya untuk hari ini s/d {MAX_KOREKSI_HARI} hari ke belakang",
                              {"tanggal_mulai": "di luar batas"})
    jenis_absen = data.get("jenis_absen")
    if jenis_absen not in ("masuk", "pulang"):
        raise ValidationError("jenis_absen wajib masuk/pulang", {"jenis_absen": "masuk|pulang"})
    try:
        jam = time.fromisoformat(data.get("jam_koreksi") or "")
    except ValueError:
        raise ValidationError("Format jam_koreksi HH:MM", {"jam_koreksi": "HH:MM"})
    if jenis_absen in _today_rows(ctx["id_pegawai"], tanggal):
        raise ValidationError(f"Absen {jenis_absen} pada tanggal tersebut sudah tercatat")
    if query.count_koreksi_aktif(ctx["id_pegawai"], tanggal, jenis_absen):
        raise ValidationError("Sudah ada pengajuan koreksi yang sama")
    return {"id_jenis_izin": None, "jenis_absen": jenis_absen, "jam_koreksi": jam,
            "tanggal_mulai": tanggal, "tanggal_selesai": tanggal}, False


def ajukan_perizinan(id_user, data, lampiran):
    today = get_wita().date()
    ctx = _context(id_user, today)
    alasan = (data.get("alasan") or "").strip()
    if not alasan:
        raise ValidationError("Alasan wajib diisi", {"alasan": "required"})
    clean = _clean_izin if data.get("jenis_pengajuan") == "izin" else _clean_koreksi
    row, butuh_lampiran = clean(ctx, data, today)
    isi, ext = _lampiran(lampiran)
    if butuh_lampiran and not isi:
        raise ValidationError("Jenis izin ini wajib melampirkan bukti", {"lampiran": "required"})

    path = storage.save_file(isi, f"perizinan/{today:%Y-%m}", ext) if isi else None
    row.update({"id_pegawai": ctx["id_pegawai"], "jenis_pengajuan": data["jenis_pengajuan"],
                "alasan": alasan, "lampiran_path": path})
    try:
        id_perizinan = query.insert_perizinan(row, id_user)
    except Exception:
        storage.delete_file(path)
        raise
    return get_perizinan(id_user, id_perizinan)


def list_perizinan(id_user, args):
    ctx = _context(id_user, get_wita().date())
    return query.get_perizinan_list(ctx["id_pegawai"], args.get("status"), args.get("tahun"))


def _own_perizinan(id_user, id_perizinan):
    ctx = _context(id_user, get_wita().date())
    row = query.get_perizinan(id_perizinan)
    if not row or row["id_pegawai"] != ctx["id_pegawai"]:
        raise NotFoundError("Pengajuan tidak ditemukan")
    return ctx, row


def get_perizinan(id_user, id_perizinan):
    return {k: v for k, v in _own_perizinan(id_user, id_perizinan)[1].items() if k != "lampiran_path"}


def batal_perizinan(id_user, id_perizinan):
    ctx, row = _own_perizinan(id_user, id_perizinan)
    if not query.batal_perizinan(id_perizinan, ctx["id_pegawai"], id_user):
        raise ValidationError(f"Pengajuan berstatus {row['status']} tidak bisa dibatalkan")
    return get_perizinan(id_user, id_perizinan)


def lampiran_path(id_user, id_perizinan):
    """Kembalikan (path_absolut, mimetype)."""
    row = _own_perizinan(id_user, id_perizinan)[1]
    full = row["lampiran_path"] and storage.full_path(row["lampiran_path"])
    if not full or not os.path.exists(full):
        raise NotFoundError("Lampiran tidak ada")
    return full, "application/pdf" if full.endswith(".pdf") else "image/jpeg"
