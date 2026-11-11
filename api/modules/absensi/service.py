# api/modules/absensi/service.py
"""
Ketentuan absensi (semua waktu = jam server WITA, bukan jam HP):

1. Akun harus tertaut ke pegawai aktif yang sudah punya foto wajah (embedding) dan jadwal kerja.
2. Jadwal  : bukan hari libur aktif, dan hari ini hari kerja di jadwal_harian.
   - masuk  : dibuka ABSEN_MASUK_BUKA_MENIT sebelum jam masuk, ditutup saat jam pulang.
              Lewat jam masuk + toleransi -> status 'terlambat', terlambat_menit dihitung dari jam masuk.
   - pulang : boleh jika sudah absen masuk, atau (lupa masuk) jam pulang sudah lewat. Sampai akhir hari.
              Sebelum jam pulang -> status 'pulang_cepat'.
   - Masing-masing hanya 1x per hari.
3. GPS     : akurasi <= GPS_MAX_AKURASI_METER, dan di dalam radius lokasi kantor
             (lokasi pegawai, atau lokasi aktif terdekat jika pegawai tidak diikat ke satu lokasi).
4. Wajah   : foto harus berisi tepat 1 wajah dan cocok dgn foto enrollment (jarak <= FACE_MATCH_THRESHOLD).
Urutan cek: akun -> jadwal -> GPS -> wajah (yang murah dulu). Setiap kegagalan dicatat ke absensi_gagal.
"""
import os
from datetime import date, timedelta

from api.core import storage
from api.modules.master.jadwal_kerja.service import HARI
from api.shared.exceptions import AppError, ForbiddenError, NotFoundError, ValidationError
from api.utils.datetime import get_wita
from api.utils.face import FaceError, face_distance, process_face_photo
from api.utils.geo import haversine_m
from . import query

# default; bisa ditimpa lewat tabel settings (key sama)
DEFAULT_SETTINGS = {
    "ABSEN_MASUK_BUKA_MENIT": 60,
    "GPS_MAX_AKURASI_METER": 50,
    "FACE_MATCH_THRESHOLD": 0.5,
}
MAX_RANGE_HARI = 62


class AbsenError(AppError):
    def __init__(self, code, message):
        super().__init__(message=message, code=code, status_code=422)


def _settings():
    return {**DEFAULT_SETTINGS, **query.get_settings(DEFAULT_SETTINGS)}


def _fail(ctx, stage, code, message, **extra):
    """Catat ke absensi_gagal lalu raise. Pencatatan transaksi sendiri, jadi tetap tersimpan."""
    query.insert_gagal({"id_pegawai": ctx["id_pegawai"], "source": "server", "stage": stage,
                        "error_code": code, "error_message": message, **extra})
    raise AbsenError(code, message)


def _context(id_user, tanggal):
    ctx = query.get_context(id_user, tanggal)
    if not ctx:
        raise ForbiddenError("Akun tidak tertaut ke data pegawai")
    if ctx["is_active"] != 1:
        raise ForbiddenError("Pegawai tidak aktif")
    return ctx


def _today_rows(id_pegawai, tanggal):
    return {r["jenis"]: r for r in query.get_range(tanggal, tanggal, id_pegawai)}


def _jadwal_hari_ini(ctx, now):
    """Kembalikan (jam_masuk_dt, jam_pulang_dt) atau (None, alasan_code, pesan)."""
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
            _fail(ctx, "SCHEDULE", "OUTSIDE_TIME_WINDOW",
                  f"Absen masuk dibuka pukul {buka:%H:%M}", jenis=jenis)
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
    lokasi = query.get_lokasi_aktif(ctx["id_lokasi_kantor"])
    if not lokasi:
        _fail(ctx, "LOCATION", "NO_OFFICE_LOCATION", "Lokasi kantor belum diatur", **gps)
    jarak, lk = min((haversine_m(lat, lon, lk["latitude"], lk["longitude"]), lk) for lk in lokasi)
    jarak = round(jarak, 2)
    if jarak > lk["radius_meter"]:
        _fail(ctx, "LOCATION", "OUTSIDE_RADIUS",
              f"Di luar area {lk['name']} ({jarak:.0f} m, maks {lk['radius_meter']} m)",
              id_lokasi_kantor=lk["id_lokasi_kantor"], jarak_meter=jarak, **gps)
    return lk, jarak


def _cek_wajah(ctx, jenis, foto, gps, cfg):
    """Kembalikan (jpeg, skor). Foto gagal-cocok disimpan untuk audit."""
    try:
        jpeg, embedding = process_face_photo(foto)
    except FaceError as e:
        _fail(ctx, "FACE", "FACE_NOT_DETECTED", str(e), jenis=jenis, **gps)
    dist = face_distance(ctx["embedding"], embedding)
    skor = round(max(0.0, 1 - dist), 4)
    if dist > float(cfg["FACE_MATCH_THRESHOLD"]):
        path = storage.save_file(jpeg, f"absensi_gagal/{get_wita():%Y-%m}", "jpg")
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

    path = storage.save_file(jpeg, f"absensi/{now:%Y-%m}", "jpg")
    data = {"id_pegawai": ctx["id_pegawai"], "tanggal": tanggal, "jenis": jenis, "waktu_absen": now,
            "skor_wajah": skor, "photo_path": path, **gps, **jadwal}
    try:
        id_absensi = query.insert(data)
    except Exception:
        storage.delete_file(path)
        raise
    if id_absensi is None:  # double submit bersamaan
        storage.delete_file(path)
        raise AbsenError("ALREADY_CHECKED", f"Sudah absen {jenis} hari ini")
    return get(id_absensi)


def status_hari_ini(id_user):
    """Info untuk layar absen: jadwal hari ini, yang sudah dilakukan, lokasi kantor."""
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
        "keterangan": msg,
        "kode": code,
        "jadwal": jadwal and {
            "nama": ctx["jadwal_kerja_name"],
            "masuk": jadwal[0].time(), "pulang": jadwal[1].time(),
            "masuk_dibuka": (jadwal[0] - timedelta(minutes=int(cfg["ABSEN_MASUK_BUKA_MENIT"]))).time(),
            "toleransi_terlambat_menit": ctx["toleransi_terlambat_menit"],
        },
        "masuk": done.get("masuk"),
        "pulang": done.get("pulang"),
        "lokasi": query.get_lokasi_aktif(ctx["id_lokasi_kantor"]),
        "gps_max_akurasi_meter": cfg["GPS_MAX_AKURASI_METER"],
    }


def lapor_gagal_client(id_user, data):
    ctx = _context(id_user, get_wita().date())
    detail = data.get("detail")
    if detail is not None and not isinstance(detail, dict):
        raise ValidationError("detail harus object", {"detail": "object"})
    query.insert_gagal({**data, "id_pegawai": ctx["id_pegawai"], "source": "client",
                        "error_message": (data.get("error_message") or "")[:500] or None})


def _range(args):
    today = get_wita().date()
    try:
        mulai = date.fromisoformat(args["tanggal_mulai"]) if args.get("tanggal_mulai") else today
        selesai = date.fromisoformat(args["tanggal_selesai"]) if args.get("tanggal_selesai") else mulai
    except ValueError:
        raise ValidationError("Format tanggal YYYY-MM-DD")
    if selesai < mulai:
        raise ValidationError("tanggal_selesai harus >= tanggal_mulai")
    if (selesai - mulai).days >= MAX_RANGE_HARI:
        raise ValidationError(f"Rentang maksimal {MAX_RANGE_HARI} hari")
    return mulai, selesai


def riwayat_saya(id_user, args):
    ctx = _context(id_user, get_wita().date())
    return query.get_range(*_range(args), ctx["id_pegawai"])


def list_all(args):
    return query.get_range(*_range(args), args.get("id_pegawai"))


def list_gagal(args):
    return query.get_gagal_range(*_range(args), args.get("id_pegawai"))


def get(id_absensi):
    row = query.get_by_id(id_absensi)
    if not row:
        raise NotFoundError("Absensi tidak ditemukan")
    return {k: v for k, v in row.items() if k != "photo_path"}


def _file(rel):
    full = rel and storage.full_path(rel)
    if not full or not os.path.exists(full):
        raise NotFoundError("Foto tidak ditemukan")
    return full


def foto_path(id_absensi, id_user, permissions):
    """Pemilik absensi atau pemegang absensi.view_all."""
    row = query.get_by_id(id_absensi)
    if not row:
        raise NotFoundError("Absensi tidak ditemukan")
    if not ({"*", "absensi.view_all"} & permissions):
        ctx = query.get_context(id_user, row["tanggal"])
        if not ctx or ctx["id_pegawai"] != row["id_pegawai"]:
            raise ForbiddenError("Akses tidak diizinkan")
    return _file(row["photo_path"])


def foto_gagal_path(id_absensi_gagal):
    return _file(query.get_gagal_photo(id_absensi_gagal))
