# api/modules/master/ref_options/service.py
"""Daftar pilihan sederhana. Tabel lain menyimpan `code`, bukan id.
Opsi bawaan (is_system = 1, dari seed migrasi): group_code & code tetap, tidak bisa dinonaktifkan; label & urutan boleh diubah.
Kode opsi yang sudah dipakai data lain sebaiknya tidak diubah — data lama tetap menyimpan kode lama."""
from api.shared.exceptions import NotFoundError, ValidationError
from . import query


def _clean(data, current=None):
    group_code = data["group_code"].strip().upper()
    code = data["code"].strip().upper()
    label = data["label"].strip()
    if not group_code or not code or not label:
        raise ValidationError("Grup, kode & label wajib diisi",
                              {"group_code": "required", "code": "required", "label": "required"})
    if current and current["is_system"] == 1 and (group_code, code) != (current["group_code"], current["code"]):
        raise ValidationError("Grup & kode opsi bawaan tidak bisa diubah", {"code": "Opsi bawaan"})
    dup = query.find_by_code(group_code, code, current["id_ref_option"] if current else None)
    if dup:
        hint = "" if dup["is_active"] == 1 else " (nonaktif, aktifkan kembali saja)"
        raise ValidationError("Kode sudah dipakai di grup ini" + hint, {"code": "Sudah dipakai"})
    return {"group_code": group_code, "code": code, "label": label, "sort_order": data.get("sort_order") or 0}


def list_all(group_code=None, include_inactive=0):
    return query.get_all(group_code.strip().upper() if group_code else None, include_inactive)


def get(id_ref_option):
    row = query.get_by_id(id_ref_option)
    if not row:
        raise NotFoundError("Opsi tidak ditemukan")
    return row


def validate_codes(values):
    """Dipakai modul lain. values = {field: (group_code, code)}; code kosong dilewati.
    Raise ValidationError berisi field yang kodenya tidak ada / nonaktif."""
    filled = {f: (g, c) for f, (g, c) in values.items() if c}
    if not filled:
        return
    active = query.get_active_codes({g for g, _ in filled.values()})
    errors = {f: f"Pilihan tidak valid ({g})" for f, (g, c) in filled.items() if c not in active[g]}
    if errors:
        raise ValidationError("Pilihan tidak valid", errors)


def create(data, id_user):
    return get(query.insert(_clean(data), id_user))


def update(id_ref_option, data, id_user):
    current = get(id_ref_option)
    query.update(id_ref_option, _clean(data, current), id_user)
    return get(id_ref_option)


def deactivate(id_ref_option, id_user):
    if get(id_ref_option)["is_system"] == 1:
        raise ValidationError("Opsi bawaan tidak bisa dinonaktifkan")
    query.set_active(id_ref_option, 0, id_user)


def activate(id_ref_option, id_user):
    get(id_ref_option)
    query.set_active(id_ref_option, 1, id_user)
    return get(id_ref_option)
