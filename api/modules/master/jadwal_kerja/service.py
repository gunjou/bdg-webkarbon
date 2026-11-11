# api/modules/master/jadwal_kerja/service.py
import json
from datetime import datetime

from api.shared.exceptions import NotFoundError, ValidationError
from . import query

HARI = ("senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "minggu")


def _jam(value):
    """'7:30' / '07:30' -> '07:30'; None jika format salah."""
    try:
        return datetime.strptime(str(value).strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


def _clean_jadwal(jadwal):
    """Normalisasi ke 7 hari lengkap; hari tidak diisi = null (libur)."""
    if not isinstance(jadwal, dict):
        raise ValidationError("jadwal_harian harus berupa object", {"jadwal_harian": "object"})
    errors = {}
    unknown = [k for k in jadwal if str(k).lower() not in HARI]
    if unknown:
        errors["hari"] = f"Hari tidak dikenal: {', '.join(map(str, unknown))}"
    jadwal = {str(k).lower(): v for k, v in jadwal.items()}

    result = {}
    for hari in HARI:
        val = jadwal.get(hari)
        if val is None:
            result[hari] = None
            continue
        if not isinstance(val, dict):
            errors[hari] = "Harus {masuk, pulang} atau null"
            continue
        masuk, pulang = _jam(val.get("masuk")), _jam(val.get("pulang"))
        if not masuk or not pulang:
            errors[hari] = "masuk & pulang wajib format HH:MM"
        elif masuk >= pulang:  # string HH:MM bisa dibandingkan langsung
            errors[hari] = "Jam masuk harus sebelum jam pulang"
        else:
            result[hari] = {"masuk": masuk, "pulang": pulang}

    if errors:
        raise ValidationError("Jadwal harian tidak valid", errors)
    if not any(result.values()):
        raise ValidationError("Minimal 1 hari kerja", {"jadwal_harian": "Semua hari libur"})
    return result


def _clean(data, id_jadwal_kerja=None):
    name = data["name"].strip()
    if not name:
        raise ValidationError("Nama jadwal wajib diisi", {"name": "required"})
    if query.find_active_by_name(name, id_jadwal_kerja):
        raise ValidationError("Nama jadwal sudah dipakai", {"name": "Sudah dipakai"})
    return {
        "name": name,
        "jadwal_harian": json.dumps(_clean_jadwal(data["jadwal_harian"])),
        "toleransi_terlambat_menit": data.get("toleransi_terlambat_menit") or 0,
    }


def list_all():
    return query.get_all()


def get(id_jadwal_kerja):
    row = query.get_by_id(id_jadwal_kerja)
    if not row:
        raise NotFoundError("Jadwal kerja tidak ditemukan")
    return row


def create(data, id_user):
    return get(query.insert(_clean(data), id_user))


def update(id_jadwal_kerja, data, id_user):
    get(id_jadwal_kerja)
    query.update(id_jadwal_kerja, _clean(data, id_jadwal_kerja), id_user)
    return get(id_jadwal_kerja)


def deactivate(id_jadwal_kerja, id_user):
    get(id_jadwal_kerja)
    used = query.count_active_pegawai(id_jadwal_kerja)
    if used:
        raise ValidationError(f"Jadwal masih dipakai {used} pegawai aktif")
    query.set_active(id_jadwal_kerja, 0, id_user)


def activate(id_jadwal_kerja, id_user):
    row = get(id_jadwal_kerja)
    if query.find_active_by_name(row["name"], id_jadwal_kerja):
        raise ValidationError("Sudah ada jadwal aktif dengan nama yang sama")
    query.set_active(id_jadwal_kerja, 1, id_user)
    return get(id_jadwal_kerja)
