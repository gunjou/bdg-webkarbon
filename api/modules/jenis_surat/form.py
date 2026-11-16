# api/modules/jenis_surat/form.py
"""Validasi & normalisasi surat.data terhadap skema_form (bentuk data: lihat docstring render.py).
strict=False (simpan draft): hanya cek format, isian boleh belum lengkap.
strict=True  (terbitkan)   : field required, nama di section penduduk, dan teks_bebas required wajib terisi.
Kode ref_options dicek lewat `check_codes(values)` (dioper service, agar file ini tanpa DB)."""
import re
from datetime import date

from api.shared.exceptions import ValidationError
from api.utils.template import sanitize_html

TEXT_MAX = 2000
ORANG_TEXT = {"nama": 150, "tempat_lahir": 100, "alamat": 255}
ORANG_REF = {"agama": "AGAMA", "pekerjaan": "PEKERJAAN", "status_perkawinan": "STATUS_PERKAWINAN",
             "kewarganegaraan": "KEWARGANEGARAAN", "dusun": "DUSUN"}


def _str(v):
    return str(v).strip() if v not in (None, "") else ""


def _date(v):
    return date.fromisoformat(_str(v)[:10]).isoformat()


def _nilai(f, v, errors, path, codes):
    v = _str(v) if not isinstance(v, (int, float)) or isinstance(v, bool) else v
    if v in ("", None):
        return None
    try:
        if f["type"] in ("text", "textarea"):
            if len(v) > TEXT_MAX:
                raise ValueError(f"Maks {TEXT_MAX} karakter")
            return v
        if f["type"] == "number":
            n = float(str(v).replace(",", "."))
            return int(n) if n.is_integer() else n
        if f["type"] == "rupiah":
            n = int(float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) else v)
            if n < 0:
                raise ValueError("Tidak boleh negatif")
            return n
        if f["type"] == "date":
            return _date(v)
        if f["type"] == "select":
            if f.get("options_group"):
                codes[path] = (f["options_group"], str(v).upper())
                return str(v).upper()
            if v not in f["options"]:
                raise ValueError("Pilihan tidak valid")
            return v
    except ValueError as e:
        errors[path] = str(e) if str(e) and not str(e).startswith(("could not", "invalid")) else "Format tidak valid"
    return None


def _orang(raw, path, errors, codes, strict):
    raw = raw if isinstance(raw, dict) else {}
    o = {}
    for k, mx in ORANG_TEXT.items():
        o[k] = _str(raw.get(k)) or None
        if o[k] and len(o[k]) > mx:
            errors[f"{path}.{k}"] = f"Maks {mx} karakter"
    for k in ("nik", "no_kk"):
        o[k] = _str(raw.get(k)) or None
        if o[k] and not re.fullmatch(r"[0-9]{16}", o[k]):
            errors[f"{path}.{k}"] = "16 digit angka"
    for k in ("rt", "rw"):
        o[k] = _str(raw.get(k)) or None
        if o[k]:
            if o[k].isdigit() and len(o[k]) <= 3:
                o[k] = o[k].zfill(3)
            else:
                errors[f"{path}.{k}"] = "Maks 3 digit angka"
    o["jenis_kelamin"] = _str(raw.get("jenis_kelamin")).upper() or None
    if o["jenis_kelamin"] not in (None, "L", "P"):
        errors[f"{path}.jenis_kelamin"] = "L / P"
    o["tanggal_lahir"] = None
    if _str(raw.get("tanggal_lahir")):
        try:
            o["tanggal_lahir"] = _date(raw["tanggal_lahir"])
        except ValueError:
            errors[f"{path}.tanggal_lahir"] = "Format YYYY-MM-DD"
    for k, g in ORANG_REF.items():
        o[k] = _str(raw.get(k)).upper() or None
        if o[k]:
            codes[f"{path}.{k}"] = (g, o[k])
    o["id_penduduk"] = None
    if raw.get("id_penduduk") not in (None, ""):
        try:
            o["id_penduduk"] = int(raw["id_penduduk"])
        except (TypeError, ValueError):
            errors[f"{path}.id_penduduk"] = "Harus angka"
    if strict and not o["nama"]:
        errors[f"{path}.nama"] = "Wajib diisi"
    return o


def validate_data(skema, data, check_codes, strict=False):
    """Kembalikan data bersih (key di luar skema dibuang). Raise ValidationError {path: pesan}."""
    data = data if isinstance(data, dict) else {}
    out, errors, codes = {}, {}, {}
    for s in skema["sections"]:
        k = s["key"]
        if s["type"] == "penduduk":
            out[k] = _orang(data.get(k), k, errors, codes, strict)
        elif s["type"] == "fields":
            for f in s["fields"]:
                out[f["key"]] = _nilai(f, data.get(f["key"]), errors, f["key"], codes)
                if strict and f.get("required") and out[f["key"]] is None and f["key"] not in errors:
                    errors[f["key"]] = "Wajib diisi"
        elif s["type"] == "daftar":
            rows = data.get(k) if isinstance(data.get(k), list) else []
            out[k] = []
            for r in rows:
                r = r if isinstance(r, dict) else {}
                i = len(out[k])
                row = {c["key"]: _nilai(c, r.get(c["key"]), errors, f"{k}[{i}].{c['key']}", codes) for c in s["columns"]}
                if any(v is not None for v in row.values()):  # baris kosong dibuang
                    if strict:
                        for c in s["columns"]:
                            if c.get("required") and row[c["key"]] is None:
                                errors.setdefault(f"{k}[{i}].{c['key']}", "Wajib diisi")
                    out[k].append(row)
        else:
            out[k] = sanitize_html(_str(data.get(k))) or None
            if strict and s.get("required") and not out[k]:
                errors[k] = "Wajib diisi"
    if codes:
        try:
            check_codes(codes)
        except ValidationError as e:
            errors.update(e.errors or {})
    if errors:
        raise ValidationError("Isian surat belum valid", errors)
    return out


def pemohon(skema, data):
    """(section key, data orang) pemohon utama = section penduduk pertama."""
    k = next(s["key"] for s in skema["sections"] if s["type"] == "penduduk")
    return k, data.get(k) or {}
