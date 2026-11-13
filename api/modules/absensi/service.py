# api/modules/absensi/service.py
"""
Aplikasi ADMIN: monitoring presensi, rekap, log gagal, koreksi absen, review perizinan.

Status harian pegawai (urutan menentukan):
  izin (izin disetujui mencakup tanggal) -> hadir (ada absen masuk/pulang) -> libur (hari_libur aktif)
  -> bukan_hari_kerja (jadwal hari itu null / tanpa jadwal) -> alpha (tanggal sudah lewat) -> belum_absen (hari ini).
  Izin yang masih 'diajukan' tidak membebaskan dari alpha. Jadwal = jadwal pegawai SAAT INI (tidak ada histori).

Koreksi absen (admin langsung, atau persetujuan pengajuan koreksi pegawai):
  upsert absensi per (pegawai, tanggal, jenis): waktu = tanggal + jam (WITA). Status dihitung dari jadwal pegawai
  SAAT INI dgn aturan sama seperti presensi: masuk lewat jam masuk + toleransi -> terlambat (menit dari jam masuk);
  pulang sebelum jam pulang -> pulang_cepat. Ditolak jika tanggal hari libur aktif / bukan hari kerja. Ditandai is_koreksi karena created_by/updated_by bukan akun
  pegawai itu sendiri. GPS/foto kosong pada absen yang dibuat lewat koreksi.

Tambah izin oleh admin: aturan sama dgn pengajuan pegawai (jenis aktif, maks 30 hari, tidak bentrok, lampiran
  wajib jika jenis butuh_lampiran), tanpa batas tanggal; langsung 'disetujui' dgn peninjau = admin pembuat.

Review perizinan: hanya status 'diajukan'; tidak boleh meninjau pengajuan sendiri; ditolak wajib catatan.
"""
import calendar
import os
from datetime import date, datetime, time, timedelta

from api.core import storage
from api.modules.master.jadwal_kerja.service import HARI
from api.modules.presensi import service as presensi  # aturan izin dipakai bersama
from api.shared.exceptions import ForbiddenError, NotFoundError, ValidationError
from api.utils.datetime import WITA, get_wita
from . import query

MAX_RANGE_HARI = 62


# ---------------- helper ----------------
def _tgl(value, field, default):
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError("Format tanggal YYYY-MM-DD", {field: "YYYY-MM-DD"})


def _range(args, default_mulai=None):
    today = get_wita().date()
    mulai = _tgl(args.get("tanggal_mulai"), "tanggal_mulai", default_mulai or today)
    selesai = _tgl(args.get("tanggal_selesai"), "tanggal_selesai", today if default_mulai else mulai)
    if selesai < mulai:
        raise ValidationError("tanggal_selesai harus >= tanggal_mulai")
    if (selesai - mulai).days >= MAX_RANGE_HARI:
        raise ValidationError(f"Rentang maksimal {MAX_RANGE_HARI} hari")
    return mulai, selesai


def _file(rel, pesan):
    full = rel and storage.full_path(rel)
    if not full or not os.path.exists(full):
        raise NotFoundError(pesan)
    return full


def _status_hari(peg, tgl, absen, izin, libur, today):
    if izin and izin["status"] == "disetujui":
        return "izin"
    if absen:
        return "hadir"
    if tgl in libur:
        return "libur"
    if not (peg["jadwal_harian"] or {}).get(HARI[tgl.weekday()]):
        return "bukan_hari_kerja"
    return "alpha" if tgl < today else "belum_absen"


def _index(mulai, selesai, id_pegawai, izin_status):
    """absen[(id_pegawai, tanggal)] = {jenis: row}; izin(id_pegawai, tanggal) -> row/None; libur {tanggal: nama}."""
    absen = {}
    for r in query.get_absensi_range(mulai, selesai, id_pegawai):
        absen.setdefault((r["id_pegawai"], r["tanggal"]), {})[r["jenis"]] = r
    izin_rows = sorted(query.get_izin_range(mulai, selesai, izin_status, id_pegawai),
                       key=lambda z: z["status"] != "disetujui")  # disetujui didahulukan

    def izin(id_pegawai, tgl):
        return next((z for z in izin_rows if z["id_pegawai"] == id_pegawai
                     and z["tanggal_mulai"] <= tgl <= z["tanggal_selesai"]), None)

    return absen, izin, query.get_libur(mulai, selesai)


# ---------------- presensi ----------------
def harian(args):
    today = get_wita().date()
    tgl = _tgl(args.get("tanggal"), "tanggal", today)
    absen, izin, libur = _index(tgl, tgl, None, ("diajukan", "disetujui"))
    result = []
    for peg in query.get_pegawai_aktif():
        rows = absen.get((peg["id_pegawai"], tgl), {})
        z = izin(peg["id_pegawai"], tgl)
        result.append({
            "id_pegawai": peg["id_pegawai"], "full_name": peg["full_name"], "nip": peg["nip"],
            "jabatan_name": peg["jabatan_name"],
            "status_hari": _status_hari(peg, tgl, rows, z, libur, today),
            "keterangan": libur.get(tgl),
            "jadwal": (peg["jadwal_harian"] or {}).get(HARI[tgl.weekday()]),
            "masuk": rows.get("masuk"), "pulang": rows.get("pulang"), "izin": z,
        })
    return {"tanggal": tgl, "pegawai": result}


def list_absensi(args):
    return query.get_absensi_range(*_range(args), args.get("id_pegawai"), args.get("status"))


def get_absensi(id_absensi):
    row = query.get_absensi(id_absensi)
    if not row:
        raise NotFoundError("Absensi tidak ditemukan")
    return {k: v for k, v in row.items() if k != "photo_path"}


def foto_absensi(id_absensi):
    row = query.get_absensi(id_absensi)
    if not row:
        raise NotFoundError("Absensi tidak ditemukan")
    return _file(row["photo_path"], "Foto tidak ada (absen hasil koreksi tidak punya foto)")


def rekap(args):
    today = get_wita().date()
    try:
        y, m = map(int, (args.get("bulan") or f"{today:%Y-%m}").split("-"))
        mulai = date(y, m, 1)
    except ValueError:
        raise ValidationError("Format bulan YYYY-MM", {"bulan": "YYYY-MM"})
    selesai = min(date(y, m, calendar.monthrange(y, m)[1]), today)
    if selesai < mulai:
        raise ValidationError("Bulan belum berjalan", {"bulan": "masa depan"})

    absen, izin, libur = _index(mulai, selesai, args.get("id_pegawai"), ("disetujui",))
    result = []
    for peg in query.get_pegawai_aktif(args.get("id_pegawai")):
        r = {"id_pegawai": peg["id_pegawai"], "full_name": peg["full_name"], "nip": peg["nip"],
             "jabatan_name": peg["jabatan_name"], "hari_kerja": 0, "hadir": 0, "terlambat": 0,
             "terlambat_menit": 0, "pulang_cepat": 0, "tanpa_masuk": 0, "tanpa_pulang": 0, "izin": 0,
             "izin_per_jenis": {}, "alpha": 0, "libur": 0}
        tgl = mulai
        while tgl <= selesai:
            rows = absen.get((peg["id_pegawai"], tgl), {})
            z = izin(peg["id_pegawai"], tgl)
            st = _status_hari(peg, tgl, rows, z, libur, today)
            kerja = tgl not in libur and (peg["jadwal_harian"] or {}).get(HARI[tgl.weekday()])
            r["hari_kerja"] += 1 if kerja else 0
            if st == "hadir":
                r["hadir"] += 1
                masuk, pulang = rows.get("masuk"), rows.get("pulang")
                if masuk and masuk["status"] == "terlambat":
                    r["terlambat"] += 1
                    r["terlambat_menit"] += masuk["terlambat_menit"]
                if pulang and pulang["status"] == "pulang_cepat":
                    r["pulang_cepat"] += 1
                r["tanpa_masuk"] += 0 if masuk else 1
                r["tanpa_pulang"] += 0 if pulang or tgl == today else 1
            elif st == "izin":
                r["izin"] += 1
                r["izin_per_jenis"][z["jenis_izin_code"]] = r["izin_per_jenis"].get(z["jenis_izin_code"], 0) + 1
            elif st in ("alpha", "libur"):
                r[st] += 1
            tgl += timedelta(days=1)
        result.append(r)
    return {"bulan": f"{mulai:%Y-%m}", "tanggal_mulai": mulai, "tanggal_selesai": selesai, "pegawai": result}


def _jam(value):
    try:
        return time.fromisoformat(value or "")
    except ValueError:
        raise ValidationError("Format jam HH:MM", {"jam": "HH:MM"})


def _koreksi_row(id_pegawai, tanggal, jenis, jam):
    peg = next(iter(query.get_pegawai_aktif(id_pegawai)), None)
    if not peg:
        raise ValidationError("Pegawai tidak ditemukan / tidak aktif", {"id_pegawai": "tidak valid"})
    libur = query.get_libur(tanggal, tanggal)
    if tanggal in libur:
        raise ValidationError(f"Tanggal tersebut hari libur: {libur[tanggal]}", {"tanggal": "hari libur"})
    hari = (peg["jadwal_harian"] or {}).get(HARI[tanggal.weekday()])
    if not hari:
        raise ValidationError("Tanggal tersebut bukan hari kerja menurut jadwal pegawai", {"tanggal": "bukan hari kerja"})
    jadwal = time.fromisoformat(hari[jenis])
    telat = (jam.hour * 60 + jam.minute) - (jadwal.hour * 60 + jadwal.minute)
    if jenis == "masuk":
        status = "terlambat" if telat > int(peg["toleransi_terlambat_menit"] or 0) else "tepat_waktu"
    else:
        status = "pulang_cepat" if jam < jadwal else "tepat_waktu"
    return {"id_pegawai": id_pegawai, "tanggal": tanggal, "jenis": jenis, "jam_jadwal": jadwal,
            "waktu_absen": datetime.combine(tanggal, jam, tzinfo=WITA),
            "status": status, "terlambat_menit": telat if status == "terlambat" else 0}


def koreksi(data, id_user):
    today = get_wita().date()
    tanggal = _tgl(data.get("tanggal"), "tanggal", None)
    if not tanggal or tanggal > today:
        raise ValidationError("Tanggal wajib dan tidak boleh di masa depan", {"tanggal": "tidak valid"})
    row = _koreksi_row(data["id_pegawai"], tanggal, data["jenis"], _jam(data.get("jam")))
    return get_absensi(query.upsert_koreksi(row, id_user))


# ---------------- absensi gagal ----------------
def list_gagal(args):
    return query.get_gagal_range(*_range(args), args.get("id_pegawai"), args.get("error_code"))


def foto_gagal(id_absensi_gagal):
    return _file(query.get_gagal_photo(id_absensi_gagal), "Foto tidak ditemukan")


# ---------------- perizinan ----------------
def list_perizinan(args):
    status = args.get("status") or "diajukan"  # default = antrean yang perlu ditinjau
    mulai, selesai = (date.min, date.max) if not (args.get("tanggal_mulai") or args.get("tanggal_selesai")) \
        else _range(args)
    return query.get_perizinan_list({
        "status": None if status == "semua" else status,
        "jenis_pengajuan": args.get("jenis_pengajuan"), "id_pegawai": args.get("id_pegawai"),
        "mulai": mulai, "selesai": selesai})


def _perizinan(id_perizinan):
    row = query.get_perizinan(id_perizinan)
    if not row:
        raise NotFoundError("Pengajuan tidak ditemukan")
    return row


def get_perizinan(id_perizinan):
    return {k: v for k, v in _perizinan(id_perizinan).items() if k != "lampiran_path"}


def lampiran_perizinan(id_perizinan):
    full = _file(_perizinan(id_perizinan)["lampiran_path"], "Lampiran tidak ada")
    return full, "application/pdf" if full.endswith(".pdf") else "image/jpeg"


def tambah_izin(data, lampiran, id_user):
    if not query.get_pegawai_aktif(data["id_pegawai"]):
        raise ValidationError("Pegawai tidak ditemukan / tidak aktif", {"id_pegawai": "tidak valid"})
    alasan = (data.get("alasan") or "").strip()
    if not alasan:
        raise ValidationError("Alasan wajib diisi", {"alasan": "required"})
    row, butuh_lampiran = presensi._clean_izin({"id_pegawai": data["id_pegawai"]}, data, None)
    isi, ext = presensi._lampiran(lampiran)
    if butuh_lampiran and not isi:
        raise ValidationError("Jenis izin ini wajib melampirkan bukti", {"lampiran": "required"})
    path = storage.save_file(isi, f"perizinan/{get_wita():%Y-%m}", ext) if isi else None
    try:
        id_perizinan = query.insert_izin_disetujui({**row, "id_pegawai": data["id_pegawai"], "alasan": alasan,
                                                    "lampiran_path": path}, id_user)
    except Exception:
        storage.delete_file(path)
        raise
    return get_perizinan(id_perizinan)


def review(id_perizinan, data, id_user, id_pegawai_reviewer):
    row = _perizinan(id_perizinan)
    if id_pegawai_reviewer is not None and row["id_pegawai"] == id_pegawai_reviewer:
        raise ForbiddenError("Tidak boleh meninjau pengajuan sendiri")
    if row["status"] != "diajukan":
        raise ValidationError(f"Pengajuan berstatus {row['status']} tidak bisa ditinjau")
    catatan = (data.get("catatan_peninjau") or "").strip() or None
    if data["status"] == "ditolak" and not catatan:
        raise ValidationError("Catatan wajib diisi saat menolak", {"catatan_peninjau": "required"})

    koreksi_row = None
    if data["status"] == "disetujui" and row["jenis_pengajuan"] == "koreksi":
        koreksi_row = _koreksi_row(row["id_pegawai"], row["tanggal_mulai"], row["jenis_absen"], row["jam_koreksi"])
    if not query.review_perizinan(id_perizinan, data["status"], catatan, id_user, koreksi_row):
        raise ValidationError("Pengajuan sudah ditinjau / dibatalkan")  # berubah di antara cek & update
    return get_perizinan(id_perizinan)
