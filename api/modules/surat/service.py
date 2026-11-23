# api/modules/surat/service.py
"""Surat keluar (langkah draft). Ketentuan:
- Buat draft: salin judul (name), skema_form, template_isi (-> redaksi) & versi dari jenis surat AKTIF. Render selalu memakai
  salinan ini, bukan template terkini.
- Isian (`data`) divalidasi format saat disimpan; kelengkapan (required) dicek saat terbit (strict).
  Biodata semua section penduduk selalu di-snapshot di data (terdaftar maupun manual).
  Pemohon utama = section penduduk pertama -> nama_pemohon, nik_pemohon, id_penduduk (bila dipilih dari tabel
  penduduk; harus ada). Pemohon manual TIDAK masuk ke tabel penduduk.
- Penandatangan: pegawai aktif dengan jabatan aktif can_sign = 1. atas_nama = 1 bila jabatannya bukan Kepala Desa.
- Redaksi per surat (permission surat.edit_redaksi): disanitasi & dicek terhadap skema surat ini; redaksi_diubah = 1.
  "Kembalikan" = salin template jenis surat terkini bila masih cocok dengan skema surat ini.
- Lampiran: pdf/jpg/png, boleh ditambah/dihapus selama surat belum batal & belum diarsip.
- Isian, penandatangan & redaksi diubah lewat PUT/redaksi hanya saat draft.
- Terbitkan (satu transaksi): kunci baris, isian lengkap (strict), penandatangan wajib, ambil nomor
  (terbitkan_nomor), snapshot penandatangan, render & simpan PDF, status diterbitkan. Gagal di mana pun -> rollback
  semuanya (counter ikut kembali) dan file PDF baru dihapus.
- Perbaikan setelah terbit (nomor & tanggal tetap) selama scan arsip belum di-upload; PDF dirender ulang.
- Upload scan arsip (bertanda tangan & berstempel) -> surat terkunci dari perbaikan.
- Batal (draft / diterbitkan, alasan wajib): nomor tetap melekat & hangus; counter tidak pernah mundur.
- Surat pengganti: dari surat dibatalkan yang sudah bernomor; draft baru menyalin skema, redaksi, isian &
  penandatangan surat lama (lampiran tidak), id_surat_diganti -> surat lama. Nomor baru didapat saat diterbitkan.
- Pengesahan di sistem (rencana): cukup panggil terbitkan_nomor dari langkah "sahkan"."""
import os
from datetime import date

from api.core.storage import delete_file, full_path, save_file
from api.modules.jenis_surat import service as jenis_surat_service
from api.modules.penduduk import service as penduduk_service
from api.modules.settings import service as settings_service
from api.utils.datetime import get_wita
from api.shared.exceptions import ForbiddenError, NotFoundError, ValidationError
from . import query

MAX_LIMIT = 200
JABATAN_KADES = "kepala desa"
LAMPIRAN_TYPES = {b"%PDF": ("pdf", "application/pdf"), b"\xff\xd8\xff": ("jpg", "image/jpeg"),
                  b"\x89PNG": ("png", "image/png")}
WATERMARK = {"draft": "DRAF", "dibatalkan": "DIBATALKAN"}


def get(id_surat):
    row = query.get_by_id(id_surat)
    if not row:
        raise NotFoundError("Surat tidak ditemukan")
    return row


def _draft(id_surat):
    row = get(id_surat)
    if row["status"] != "draft":
        raise ValidationError("Surat sudah tidak berstatus draft")
    return row


def search(args):
    q = (args.get("q") or "").strip()
    digits = q.isdigit()
    f = {
        "status": args.get("status") or None,
        "id_jenis_surat": args.get("id_jenis_surat"),
        "tahun": args.get("tahun"),
        "nomor": q if digits else None,
        "nama": q.lower() if q and not digits else None,
        "limit": min(max(args.get("limit") or 50, 1), MAX_LIMIT),
        "offset": max(args.get("offset") or 0, 0),
    }
    rows, total = query.search(f)
    return rows, {"total": total, "limit": f["limit"], "offset": f["offset"]}


def list_penandatangan():
    return [{**r, "atas_nama": 0 if r["jabatan"].strip().lower() == JABATAN_KADES else 1}
            for r in query.get_penandatangan()]


def _snapshot_ttd(id_pegawai):
    """(id_pegawai, atas_nama, snapshot) penandatangan yang masih sah; wajib ada."""
    if not id_pegawai:
        raise ValidationError("Penandatangan belum dipilih", {"id_penandatangan": "Wajib dipilih"})
    id_ttd, atas_nama = _penandatangan(id_pegawai)
    p = query.get_penandatangan(id_ttd)[0]
    return id_ttd, atas_nama, {"id_pegawai": id_ttd, "nama": p["full_name"], "jabatan": p["jabatan"],
                               "nip": p["nip"], "atas_nama": atas_nama}


def _penandatangan(id_pegawai):
    if id_pegawai in (None, ""):
        return None, 0
    rows = query.get_penandatangan(int(id_pegawai))
    if not rows:
        raise ValidationError("Penandatangan tidak valid", {"id_penandatangan": "Pegawai aktif dengan jabatan penandatangan"})
    return rows[0]["id_pegawai"], 0 if rows[0]["jabatan"].strip().lower() == JABATAN_KADES else 1


def _isian(skema, data):
    """Validasi data (format) + kolom pemohon utama."""
    clean = jenis_surat_service.validate_data(skema, data)
    key, p = jenis_surat_service.pemohon(skema, clean)
    if p.get("id_penduduk"):
        try:
            penduduk_service.get(p["id_penduduk"])
        except NotFoundError:
            raise ValidationError("Penduduk tidak ditemukan", {f"{key}.id_penduduk": "Tidak ditemukan"})
    return clean, {"id_penduduk": p.get("id_penduduk"), "nama_pemohon": p.get("nama") or "",
                   "nik_pemohon": p.get("nik")}


def create(data, id_user):
    jenis = jenis_surat_service.get(data.get("id_jenis_surat"))
    if jenis["is_active"] != 1:
        raise ValidationError("Jenis surat nonaktif", {"id_jenis_surat": "Nonaktif"})
    clean, pemohon = _isian(jenis["skema_form"], data.get("data"))
    return get(query.insert_draft({
        "id_jenis_surat": jenis["id_jenis_surat"], "judul": jenis["name"], **pemohon, "versi_template": jenis["versi"],
        "skema_form": jenis["skema_form"], "redaksi": jenis["template_isi"], "data": clean,
    }, id_user))


def update(id_surat, data, id_user):
    row = _draft(id_surat)
    clean, pemohon = _isian(row["skema_form"], data.get("data"))
    id_ttd, atas_nama = _penandatangan(data.get("id_penandatangan"))
    if not query.update_draft(id_surat, {**pemohon, "data": clean, "id_penandatangan": id_ttd,
                                         "atas_nama": atas_nama}, id_user):
        raise ValidationError("Surat sudah tidak berstatus draft")
    return get(id_surat)


def set_redaksi(id_surat, redaksi, id_user):
    row = _draft(id_surat)
    if not (redaksi or "").strip():
        raise ValidationError("Redaksi wajib diisi", {"redaksi": "required"})
    clean = jenis_surat_service.clean_template(redaksi, row["skema_form"])
    query.set_redaksi(id_surat, clean, 1, "redaksi_diubah", id_user)
    return get(id_surat)


def reset_redaksi(id_surat, id_user):
    row = _draft(id_surat)
    jenis = jenis_surat_service.get(row["id_jenis_surat"])
    try:
        redaksi = jenis_surat_service.clean_template(jenis["template_isi"], row["skema_form"])
    except ValidationError:
        raise ValidationError("Template standar sudah berubah dan tidak cocok dengan form surat ini")
    query.set_redaksi(id_surat, redaksi, 0, "redaksi_dikembalikan", id_user)
    return get(id_surat)


# ---------------------------------------------------------------- lampiran

def add_lampiran(id_surat, nama, file_bytes, id_user):
    row = get(id_surat)
    nama = (nama or "").strip()
    if not nama:
        raise ValidationError("Nama lampiran wajib diisi", {"nama": "required"})
    tipe = next((t for magic, t in LAMPIRAN_TYPES.items() if (file_bytes or b"").startswith(magic)), None)
    if not tipe:
        raise ValidationError("File harus PDF, JPG, atau PNG", {"file": "Tipe tidak didukung"})
    path = save_file(file_bytes, "surat/lampiran", tipe[0])
    item = {"id": os.path.splitext(os.path.basename(path))[0], "nama": nama[:150], "path": path, "mimetype": tipe[1]}
    if not query.set_lampiran(id_surat, [*row["lampiran"], item], "lampiran_ditambah", nama, id_user):
        delete_file(path)
        raise ValidationError("Lampiran tidak bisa diubah (surat batal / sudah diarsip)")
    return get(id_surat)


def _find_lampiran(row, id_lampiran):
    item = next((x for x in row["lampiran"] if x.get("id") == id_lampiran), None)
    if not item:
        raise NotFoundError("Lampiran tidak ditemukan")
    return item


def delete_lampiran(id_surat, id_lampiran, id_user):
    row = get(id_surat)
    item = _find_lampiran(row, id_lampiran)
    sisa = [x for x in row["lampiran"] if x.get("id") != id_lampiran]
    if not query.set_lampiran(id_surat, sisa, "lampiran_dihapus", item["nama"], id_user):
        raise ValidationError("Lampiran tidak bisa diubah (surat batal / sudah diarsip)")
    delete_file(item["path"])
    return get(id_surat)


def get_lampiran_file(id_surat, id_lampiran):
    item = _find_lampiran(get(id_surat), id_lampiran)
    full = full_path(item["path"])
    if not full or not os.path.exists(full):
        raise NotFoundError("File lampiran tidak ditemukan")
    return full, item["mimetype"], item["nama"]


# ---------------------------------------------------------------- preview & pdf

def preview(id_surat):
    """PDF dari salinan redaksi + data surat ini. Draft: watermark DRAF, penandatangan saat ini (belum snapshot)."""
    row = get(id_surat)
    ttd = row["data_penandatangan"]
    if not ttd and row["id_penandatangan"]:
        p = next(iter(query.get_penandatangan(row["id_penandatangan"])), None)
        ttd = p and {"nama": p["full_name"], "jabatan": p["jabatan"], "nip": p["nip"], "atas_nama": row["atas_nama"]}
    return jenis_surat_service.render_pdf(
        judul=row["judul"], redaksi=row["redaksi"], skema=row["skema_form"], data=row["data"],
        nomor=row["nomor_surat"], tanggal=row["tanggal_surat"], penandatangan=ttd,
        watermark=WATERMARK.get(row["status"]))


def get_pdf(id_surat):
    """(bytes, nama file). Diterbitkan = PDF tersimpan; draft/dibatalkan = render dengan watermark."""
    row = get(id_surat)
    nama = (row["nomor_surat"] or f"draft-{id_surat}").replace("/", "-") + ".pdf"
    if row["status"] == "diterbitkan" and row["pdf_path"]:
        full = full_path(row["pdf_path"])
        if full and os.path.exists(full):
            with open(full, "rb") as f:
                return f.read(), nama
    return preview(id_surat), nama


# ---------------------------------------------------------------- penerbitan

def format_nomor(fmt, klasifikasi, urut, kode_desa, tahun):
    return (fmt.replace("{klasifikasi}", klasifikasi).replace("{urut}", str(urut))
            .replace("{kode_desa}", kode_desa).replace("{tahun}", str(tahun)))


def terbitkan_nomor(conn, id_surat, tahun):
    """Ambil nomor urut berikutnya & susun nomor_surat. Dipanggil di DALAM transaksi penerbitan
    (nanti juga dari langkah "sahkan"). Kembalikan (nomor_urut, nomor_surat)."""
    row = query.lock(conn, id_surat)
    cfg = settings_service.get_all()
    cakupan = "GLOBAL" if cfg["surat.cakupan_nomor"] == "GLOBAL" else row["jenis_surat_code"]
    urut = query.next_nomor(conn, cakupan, tahun)
    nomor = format_nomor(cfg["surat.format_nomor"], row["kode_klasifikasi"], urut, cfg["surat.kode_desa"], tahun)
    if query.nomor_exists(conn, nomor):  # mis. format nomor diubah sehingga bentrok dengan nomor lama
        raise ValidationError(f"Nomor {nomor} sudah dipakai; periksa format nomor di pengaturan")
    return urut, nomor


def _render_simpan(row, data, redaksi, nomor, tanggal, ttd):
    pdf = jenis_surat_service.render_pdf(judul=row["judul"], redaksi=redaksi, skema=row["skema_form"], data=data,
                                         nomor=nomor, tanggal=tanggal, penandatangan=ttd)
    return save_file(pdf, "surat/pdf", "pdf")


def terbitkan(id_surat, id_user):
    get(id_surat)
    pdf_path = None
    try:
        with query.begin() as conn:
            row = query.lock(conn, id_surat)
            if row["status"] != "draft":
                raise ValidationError("Hanya draft yang bisa diterbitkan")
            data = jenis_surat_service.validate_data(row["skema_form"], row["data"], strict=True)
            id_ttd, atas_nama, ttd = _snapshot_ttd(row["id_penandatangan"])
            tanggal = get_wita().date()
            urut, nomor = terbitkan_nomor(conn, id_surat, tanggal.year)
            pdf_path = _render_simpan(row, data, row["redaksi"], nomor, tanggal, ttd)
            query.set_terbit(conn, id_surat, {
                "nomor_surat": nomor, "nomor_urut": urut, "tanggal_surat": tanggal, "data": data,
                "data_penandatangan": ttd, "id_penandatangan": id_ttd, "atas_nama": atas_nama, "pdf_path": pdf_path,
            }, id_user)
    except Exception:
        delete_file(pdf_path)
        raise
    return get(id_surat)


def _terbit_terbuka(row):
    if row["status"] != "diterbitkan":
        raise ValidationError("Hanya surat yang sudah diterbitkan")
    if row["arsip_path"]:
        raise ValidationError("Surat sudah diarsip (scan bertanda tangan sudah di-upload) dan terkunci")


def perbaiki(id_surat, data, boleh_redaksi, id_user):
    """Perbaikan & cetak ulang dengan nomor dan tanggal yang sama. data: {data, id_penandatangan?, redaksi?, catatan}."""
    catatan = (data.get("catatan") or "").strip()
    if not catatan:
        raise ValidationError("Catatan perbaikan wajib diisi", {"catatan": "required"})
    get(id_surat)
    pdf_path, lama = None, None
    try:
        with query.begin() as conn:
            row = query.lock(conn, id_surat)
            _terbit_terbuka(row)
            clean, pemohon = _isian(row["skema_form"], data["data"] if "data" in data else row["data"])
            clean = jenis_surat_service.validate_data(row["skema_form"], clean, strict=True)
            redaksi, diubah = row["redaksi"], row["redaksi_diubah"]
            if (data.get("redaksi") or "").strip() and data["redaksi"] != row["redaksi"]:
                if not boleh_redaksi:
                    raise ForbiddenError("Butuh izin surat.edit_redaksi untuk mengubah redaksi")
                redaksi, diubah = jenis_surat_service.clean_template(data["redaksi"], row["skema_form"]), 1
            id_ttd, atas_nama, ttd = _snapshot_ttd(data.get("id_penandatangan") or row["id_penandatangan"])
            pdf_path = _render_simpan(row, clean, redaksi, row["nomor_surat"], row["tanggal_surat"], ttd)
            lama = row["pdf_path"]
            query.set_perbaikan(conn, id_surat, {
                **pemohon, "data": clean, "redaksi": redaksi, "redaksi_diubah": diubah, "id_penandatangan": id_ttd,
                "atas_nama": atas_nama, "data_penandatangan": ttd, "pdf_path": pdf_path}, catatan, id_user)
    except Exception:
        delete_file(pdf_path)
        raise
    delete_file(lama)
    return get(id_surat)


def arsipkan(id_surat, file_bytes, id_user):
    tipe = next((t for magic, t in LAMPIRAN_TYPES.items() if (file_bytes or b"").startswith(magic)), None)
    if not tipe:
        raise ValidationError("Scan harus PDF, JPG, atau PNG", {"file": "Tipe tidak didukung"})
    get(id_surat)
    path = None
    try:
        with query.begin() as conn:
            _terbit_terbuka(query.lock(conn, id_surat))
            path = save_file(file_bytes, "surat/arsip", tipe[0])
            query.set_arsip(conn, id_surat, path, id_user)
    except Exception:
        delete_file(path)
        raise
    return get(id_surat)


def get_arsip_file(id_surat):
    row = get(id_surat)
    full = row["arsip_path"] and full_path(row["arsip_path"])
    if not full or not os.path.exists(full):
        raise NotFoundError("Scan arsip belum di-upload")
    ext = os.path.splitext(full)[1]
    mimetype = next(t[1] for t in LAMPIRAN_TYPES.values() if "." + t[0] == ext)
    return full, mimetype, (row["nomor_surat"] or str(id_surat)).replace("/", "-") + "-arsip" + ext


def batalkan(id_surat, alasan, id_user):
    alasan = (alasan or "").strip()
    if not alasan:
        raise ValidationError("Alasan pembatalan wajib diisi", {"alasan": "required"})
    get(id_surat)
    with query.begin() as conn:
        row = query.lock(conn, id_surat)
        if row["status"] == "dibatalkan":
            raise ValidationError("Surat sudah dibatalkan")
        query.set_batal(conn, id_surat, alasan, id_user)
    return get(id_surat)


def buat_pengganti(id_surat, id_user):
    get(id_surat)
    with query.begin() as conn:
        row = query.lock(conn, id_surat)
        if row["status"] != "dibatalkan" or not row["nomor_surat"]:
            raise ValidationError("Pengganti hanya untuk surat bernomor yang sudah dibatalkan")
        ada = query.find_pengganti(conn, id_surat)
        if ada:
            raise ValidationError(f"Surat ini sudah punya pengganti (#{ada})")
        baru = query.insert_pengganti(conn, {
            "id_jenis_surat": row["id_jenis_surat"], "judul": row["judul"], "id_penduduk": row["id_penduduk"],
            "nama_pemohon": row["nama_pemohon"], "nik_pemohon": row["nik_pemohon"], "id_surat_diganti": id_surat,
            "versi_template": row["versi_template"], "skema_form": row["skema_form"], "redaksi": row["redaksi"],
            "redaksi_diubah": row["redaksi_diubah"], "data": row["data"], "id_penandatangan": row["id_penandatangan"],
            "atas_nama": row["atas_nama"]}, id_user)
        query.add_riwayat(conn, id_surat, "diganti", f"Pengganti: surat #{baru}", id_user)
    return get(baru)


# ---------------------------------------------------------------- buku agenda & register

def _keterangan(r):
    bagian = []
    if r["status"] == "dibatalkan":
        bagian.append(f"DIBATALKAN – {r['alasan_batal']}")
    if r["nomor_pengganti"]:
        bagian.append(f"Diganti dengan {r['nomor_pengganti']}")
    elif r["id_pengganti"]:
        bagian.append(f"Pengganti dalam proses (draft #{r['id_pengganti']})")
    if r["id_surat_diganti"]:
        bagian.append(f"Pengganti dari {r['nomor_diganti']}")
    return "; ".join(bagian)


def _rows(tahun, id_jenis_surat=None):
    tahun = tahun or get_wita().year
    if not 2000 <= tahun <= 2100:
        raise ValidationError("Tahun tidak valid", {"tahun": "2000-2100"})
    rows = query.get_register(date(tahun, 1, 1), date(tahun, 12, 31), id_jenis_surat)
    return tahun, [{**{k: v for k, v in r.items() if k != "data"}, "no": i, "keterangan": _keterangan(r), "_data": r["data"]}
                   for i, r in enumerate(rows, 1)]


def agenda(tahun=None):
    """Buku Agenda Surat Keluar: semua surat bernomor dalam setahun (termasuk yang dibatalkan)."""
    tahun, rows = _rows(tahun)
    return {"tahun": tahun, "rows": [{k: v for k, v in r.items() if k != "_data"} for r in rows]}


def register(id_jenis_surat, tahun=None):
    """Buku Register per jenis surat. Kolom tambahan = field dengan "register": true di skema jenis surat
    saat ini; nilai diambil dari isian tiap surat (kode pilihan -> label)."""
    jenis = jenis_surat_service.get(id_jenis_surat)
    kolom = [f for s in jenis["skema_form"]["sections"] if s["type"] == "fields" for f in s["fields"] if f.get("register")]
    labels = jenis_surat_service.labels()
    tahun, rows = _rows(tahun, id_jenis_surat)

    def nilai(f, v):
        if v in (None, ""):
            return ""
        return labels.get(f.get("options_group"), {}).get(v, v) if f.get("options_group") else v

    out = [{**{k: v for k, v in r.items() if k != "_data"},
            "kolom": {f["key"]: nilai(f, (r["_data"] or {}).get(f["key"])) for f in kolom}} for r in rows]
    return {"tahun": tahun, "id_jenis_surat": jenis["id_jenis_surat"], "jenis_surat_code": jenis["code"],
            "jenis_surat_name": jenis["name"],
            "kolom": [{"key": f["key"], "label": f["label"], "type": f["type"]} for f in kolom], "rows": out}
