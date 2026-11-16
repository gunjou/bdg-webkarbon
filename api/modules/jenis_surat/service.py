# api/modules/jenis_surat/service.py
"""Jenis surat = cetakan: skema_form (form dinamis) + template_isi (redaksi HTML + placeholder Jinja).

skema_form  : {"sections": [...]}, 4 tipe section:
  - penduduk   : biodata 1 orang; `tampilkan` = field biodata yang dicetak. Section penduduk PERTAMA = pemohon utama
                 (wajib ada minimal satu, karena surat.nama_pemohon wajib).
  - fields     : isian biasa (`fields`), type text|textarea|number|date|rupiah|select.
  - daftar     : tabel isian berulang (`columns`, type sama dengan fields kecuali textarea).
  - teks_bebas : paragraf yang ditulis operator.
  Key section & field unik di seluruh skema (huruf kecil/angka/_), tidak boleh nama cadangan.
  Bentuk surat.data nanti: field `fields` di level atas (data[<field key>]); section penduduk/daftar/teks_bebas
  di data[<section key>].
template_isi: dibersihkan allowlist tag (nh3), hanya `{{ ... }}` (tanpa {% %} / {# #}), semua nama variabel harus
  ada di skema / data desa / helper, dan harus lolos kompilasi sandbox. Kosong = redaksi standar.
versi naik 1 setiap skema_form / template_isi berubah. Code tidak bisa diubah bila sudah ada surat
(dipakai sebagai cakupan counter nomor PER_JENIS)."""
import re

from jinja2 import TemplateError, TemplateSyntaxError, meta
from jinja2.exceptions import TemplateAssertionError

from api.modules.master.ref_options import service as ref_options_service
from api.modules.settings import service as settings_service
from api.shared.exceptions import NotFoundError, ValidationError
from api.utils.datetime import get_wita
from api.utils.template import make_env, sanitize_html
from . import form, query, render

SECTION_TYPES = ("penduduk", "fields", "daftar", "teks_bebas")
FIELD_TYPES = ("text", "textarea", "number", "date", "rupiah", "select")
COLUMN_TYPES = ("text", "number", "date", "rupiah", "select")
BIODATA = {
    "nama": "Nama", "nik": "NIK", "no_kk": "No. KK", "ttl": "Tempat/Tgl. Lahir", "jenis_kelamin": "Jenis Kelamin",
    "agama": "Agama", "status_perkawinan": "Status Perkawinan", "pekerjaan": "Pekerjaan",
    "kewarganegaraan": "Kewarganegaraan", "alamat": "Alamat",
}
HELPERS = ("biodata", "tabel", "label", "tgl_indo", "terbilang")
DESA_KEYS = {"nama": "Nama Desa", "kecamatan": "Kecamatan", "kabupaten": "Kabupaten", "alamat": "Alamat Desa"}
RESERVED = {"desa", "surat", *HELPERS, "range", "dict", "lipsum", "cycler", "joiner", "namespace", "loop", "self",
            "and", "or", "not", "in", "is", "if", "else", "true", "false", "none", "for", "import"}
KEY_RE = re.compile(r"[a-z][a-z0-9_]{0,49}")
CODE_RE = re.compile(r"[A-Z0-9_]{1,30}")
KLASIFIKASI_RE = re.compile(r"[0-9A-Za-z.\-]{1,30}")

# redaksi standar mengikuti surat asli desa
PEMBUKA = ("<p>Yang bertandatangan dibawah ini Kepala Desa {{ desa.nama }}, Kecamatan {{ desa.kecamatan }}, "
           "Kabupaten {{ desa.kabupaten }}, menerangkan dengan sebenarnya bahwa:</p>")
PENUTUP = ("<p>Demikian Surat Keterangan ini kami buat dengan sebenarnya untuk dapat dipergunakan "
           "sebagaimana mestinya.</p>")


# ---------------------------------------------------------------- skema_form

def _bool(v):
    return v is True or v == 1


def _label(item, path, errors):
    label = str(item.get("label") or "").strip()
    if not label:
        errors[f"{path}.label"] = "Wajib diisi"
    return label


def _key(item, path, errors, seen):
    key = str(item.get("key") or "").strip()
    if not KEY_RE.fullmatch(key):
        errors[f"{path}.key"] = "Huruf kecil/angka/_ , diawali huruf, maks 50"
    elif key in RESERVED:
        errors[f"{path}.key"] = "Nama cadangan, pakai nama lain"
    elif seen is not None and key in seen:
        errors[f"{path}.key"] = "Key sudah dipakai"
    elif seen is not None:
        seen.add(key)
    return key


def _field(f, path, errors, seen, types):
    if not isinstance(f, dict):
        errors[path] = "Harus object"
        return None
    out = {"key": _key(f, path, errors, seen), "label": _label(f, path, errors), "type": f.get("type")}
    if out["type"] not in types:
        errors[f"{path}.type"] = "Pilihan: " + ", ".join(types)
    if _bool(f.get("required")):
        out["required"] = True
    if _bool(f.get("register")):
        out["register"] = True
    if out["type"] == "select":
        group = str(f.get("options_group") or "").strip().upper()
        options = f.get("options")
        if group:
            if not re.fullmatch(r"[A-Z0-9_]{1,50}", group):
                errors[f"{path}.options_group"] = "Kode grup tidak valid"
            out["options_group"] = group
        elif isinstance(options, list) and options and all(isinstance(o, str) and o.strip() for o in options):
            out["options"] = [o.strip() for o in options]
        else:
            errors[f"{path}.options"] = "Isi options_group atau daftar options"
    return out


def _items(section, name, path, errors, seen, types):
    raw = section.get(name)
    if not isinstance(raw, list) or not raw:
        errors[f"{path}.{name}"] = "Minimal 1"
        return []
    return [_field(f, f"{path}.{name}[{i}]", errors, seen, types) for i, f in enumerate(raw)]


def validate_skema(skema):
    """Kembalikan skema yang sudah dinormalisasi; raise ValidationError berisi path → pesan."""
    errors = {}
    sections = skema.get("sections") if isinstance(skema, dict) else None
    if not isinstance(sections, list) or not sections:
        raise ValidationError("Skema form minimal punya 1 section", {"skema_form.sections": "Minimal 1"})
    seen, out = set(), []
    for i, s in enumerate(sections):
        path = f"skema_form.sections[{i}]"
        if not isinstance(s, dict):
            errors[path] = "Harus object"
            continue
        sec = {"key": _key(s, path, errors, seen), "label": _label(s, path, errors), "type": s.get("type")}
        if sec["type"] == "penduduk":
            tampilkan = s.get("tampilkan") or list(BIODATA)
            bad = [t for t in tampilkan if t not in BIODATA] if isinstance(tampilkan, list) else ["?"]
            if bad:
                errors[f"{path}.tampilkan"] = "Pilihan: " + ", ".join(BIODATA)
            sec["tampilkan"] = tampilkan
        elif sec["type"] == "fields":
            sec["fields"] = _items(s, "fields", path, errors, seen, FIELD_TYPES)
        elif sec["type"] == "daftar":
            sec["columns"] = _items(s, "columns", path, errors, set(), COLUMN_TYPES)  # key kolom unik per daftar
        elif sec["type"] == "teks_bebas":
            if _bool(s.get("required")):
                sec["required"] = True
        else:
            errors[f"{path}.type"] = "Pilihan: " + ", ".join(SECTION_TYPES)
        out.append(sec)
    if not any(s["type"] == "penduduk" for s in out):
        errors["skema_form.sections"] = "Wajib ada minimal 1 section penduduk (pemohon utama)"
    if errors:
        raise ValidationError("Skema form tidak valid", errors)
    return {"sections": out}


# ---------------------------------------------------------------- placeholder & template

def placeholders(skema):
    """Daftar placeholder untuk panel editor. skema harus sudah valid."""
    out = [{"token": f"{{{{ desa.{k} }}}}", "label": v, "group": "Data Desa"} for k, v in DESA_KEYS.items()]
    for s in skema["sections"]:
        g, k = s["label"], s["key"]
        if s["type"] == "penduduk":
            out.append({"token": f"{{{{ biodata({k}) }}}}", "label": f"Blok biodata {g}", "group": g})
            out += [{"token": f"{{{{ {k}.{b} }}}}", "label": BIODATA[b], "group": g} for b in s["tampilkan"]]
        elif s["type"] == "fields":
            for f in s["fields"]:
                if f["type"] == "date":
                    out.append({"token": f"{{{{ tgl_indo({f['key']}) }}}}", "label": f["label"], "group": g})
                else:
                    out.append({"token": f"{{{{ {f['key']} }}}}", "label": f["label"], "group": g})
                if f["type"] == "rupiah":
                    out.append({"token": f"{{{{ terbilang({f['key']}, \"rupiah\") }}}}",
                                "label": f"{f['label']} (terbilang)", "group": g})
        elif s["type"] == "daftar":
            out.append({"token": f"{{{{ tabel({k}) }}}}", "label": f"Tabel {g}", "group": g})
        else:
            out.append({"token": f"{{{{ {k} }}}}", "label": g, "group": g})
    return out


def variable_names(skema):
    names = {"desa", *HELPERS}
    for s in skema["sections"]:
        if s["type"] == "fields":
            names.update(f["key"] for f in s["fields"])
        else:
            names.add(s["key"])
    return names


def default_template(skema):
    pemohon = next(s["key"] for s in skema["sections"] if s["type"] == "penduduk")
    return f"{PEMBUKA}{{{{ biodata({pemohon}) }}}}{PENUTUP}"


def clean_template(html, skema):
    """Sanitasi + cek placeholder. Kembalikan HTML bersih."""
    html = (html or "").strip() or default_template(skema)
    if "{%" in html or "{#" in html:
        raise ValidationError("Redaksi hanya boleh berisi placeholder {{ ... }}", {"template_isi": "Blok {% %} / {# #} tidak diizinkan"})
    html = sanitize_html(html)
    env = make_env({h: (lambda *a, **k: "") for h in HELPERS})
    try:
        env.from_string(html)
        unknown = meta.find_undeclared_variables(env.parse(html)) - variable_names(skema)
    except (TemplateSyntaxError, TemplateAssertionError) as e:
        raise ValidationError("Placeholder tidak valid", {"template_isi": f"Baris {getattr(e, 'lineno', '?')}: {e.message}"})
    if unknown:
        raise ValidationError("Placeholder tidak ada di skema form",
                              {"template_isi": "Tidak dikenal: " + ", ".join(sorted(unknown))})
    return html


# ---------------------------------------------------------------- CRUD

def _clean_persyaratan(raw):
    out = []
    for i, p in enumerate(raw or []):
        nama = str((p or {}).get("nama") or "").strip()
        if not nama:
            raise ValidationError("Nama persyaratan wajib diisi", {f"persyaratan[{i}].nama": "required"})
        out.append({"nama": nama, "wajib": 1 if (p or {}).get("wajib") == 1 else 0})
    return out


def _clean_code(code, current=None):
    code = str(code or "").strip().upper()
    if not CODE_RE.fullmatch(code):
        raise ValidationError("Kode tidak valid", {"code": "Huruf/angka/_ , maks 30"})
    dup = query.find_by_code(code, current["id_jenis_surat"] if current else None)
    if dup:
        hint = "" if dup["is_active"] == 1 else " (nonaktif, aktifkan kembali saja)"
        raise ValidationError("Kode jenis surat sudah dipakai" + hint, {"code": "Sudah dipakai"})
    if current and code != current["code"] and query.count_surat(current["id_jenis_surat"]):
        raise ValidationError("Kode tidak bisa diubah karena sudah ada surat dengan jenis ini", {"code": "Terkunci"})
    return code


def _clean(data, current=None):
    name = str(data.get("name") or "").strip()
    klasifikasi = str(data.get("kode_klasifikasi") or "").strip()
    if not name:
        raise ValidationError("Judul surat wajib diisi", {"name": "required"})
    if not KLASIFIKASI_RE.fullmatch(klasifikasi):
        raise ValidationError("Kode klasifikasi tidak valid", {"kode_klasifikasi": "Angka/huruf/titik/strip"})
    skema = validate_skema(data.get("skema_form"))
    return {
        "code": _clean_code(data.get("code"), current),
        "name": name,
        "kode_klasifikasi": klasifikasi,
        "skema_form": skema,
        "template_isi": clean_template(data.get("template_isi"), skema),
        "persyaratan": _clean_persyaratan(data.get("persyaratan")),
        "sort_order": data.get("sort_order") or 0,
    }


def list_all(include_inactive=0):
    return query.get_all(include_inactive)


def get(id_jenis_surat):
    row = query.get_by_id(id_jenis_surat)
    if not row:
        raise NotFoundError("Jenis surat tidak ditemukan")
    return row


def get_placeholders(skema):
    return placeholders(validate_skema(skema))


def create(data, id_user):
    return get(query.insert(_clean(data), id_user))


def update(id_jenis_surat, data, id_user):
    current = get(id_jenis_surat)
    clean = _clean(data, current)
    berubah = clean["skema_form"] != current["skema_form"] or clean["template_isi"] != current["template_isi"]
    query.update(id_jenis_surat, clean, 1 if berubah else 0, id_user)
    return get(id_jenis_surat)


def duplicate(id_jenis_surat, data, id_user):
    src = get(id_jenis_surat)
    return create({**src, "code": data.get("code"), "name": data.get("name")}, id_user)


def deactivate(id_jenis_surat, id_user):
    get(id_jenis_surat)
    query.set_active(id_jenis_surat, 0, id_user)


def activate(id_jenis_surat, id_user):
    get(id_jenis_surat)
    query.set_active(id_jenis_surat, 1, id_user)
    return get(id_jenis_surat)


# ---------------------------------------------------------------- render & preview

CONTOH_ORANG = {"nama": "Lalu Ahmad Contoh", "nik": "5201010101900001", "no_kk": "5201010101900002",
                "tempat_lahir": "Karang Bongkot", "tanggal_lahir": "1990-01-01", "jenis_kelamin": "L",
                "agama": "ISLAM", "pekerjaan": "WIRASWASTA", "status_perkawinan": "BELUM_KAWIN",
                "kewarganegaraan": "WNI", "dusun": None, "rt": "001", "rw": None, "alamat": None}
CONTOH_NILAI = {"text": "Contoh isian", "textarea": "Contoh isian panjang.", "number": 2, "date": "2026-01-01",
                "rupiah": 1500000}


def _contoh_nilai(f):
    if f["type"] == "select":
        return f["options"][0] if f.get("options") else "(pilihan)"
    return CONTOH_NILAI[f["type"]]


def sample_data(skema):
    """Data contoh untuk preview wizard."""
    data = {}
    for s in skema["sections"]:
        if s["type"] == "penduduk":
            data[s["key"]] = CONTOH_ORANG
        elif s["type"] == "fields":
            data.update({f["key"]: _contoh_nilai(f) for f in s["fields"]})
        elif s["type"] == "daftar":
            data[s["key"]] = [{c["key"]: _contoh_nilai(c) for c in s["columns"]}] * 2
        else:
            data[s["key"]] = "<p>Contoh paragraf yang ditulis operator.</p>"
    return data


def labels():
    """{group_code: {code: label}}, termasuk opsi nonaktif (data lama tetap tampil labelnya)."""
    out = {}
    for r in ref_options_service.list_all(include_inactive=1):
        out.setdefault(r["group_code"], {})[r["code"]] = r["label"]
    return out


def render_pdf(*, judul, redaksi, skema, data, nomor=None, tanggal=None, penandatangan=None, watermark=None):
    """Dipakai modul surat. Error di redaksi (template user) -> ValidationError; error PDF tetap naik (500)."""
    try:
        html = render.render_html(
            judul=judul, redaksi=redaksi, skema=skema, data=data, labels=labels(),
            settings=settings_service.get_all(), logo=settings_service.get_logo_bytes(), nomor=nomor,
            tanggal=tanggal, penandatangan=penandatangan, watermark=watermark)
    except (TemplateError, TypeError, ValueError) as e:
        raise ValidationError("Redaksi gagal dirender", {"template_isi": str(e)})
    return render.to_pdf(html)


def preview(data):
    """Preview wizard: skema & redaksi boleh belum disimpan; diisi data contoh, watermark CONTOH."""
    skema = validate_skema(data.get("skema_form"))
    return render_pdf(judul=str(data.get("name") or "JUDUL SURAT"), redaksi=clean_template(data.get("template_isi"), skema),
                      skema=skema, data=sample_data(skema), watermark="CONTOH", tanggal=get_wita().date(),
                      penandatangan={"nama": "NAMA KEPALA DESA", "jabatan": "Kepala Desa", "atas_nama": 0})


# ---------------------------------------------------------------- isian surat (dipakai modul surat)

def validate_data(skema, data, strict=False):
    return form.validate_data(skema, data, ref_options_service.validate_codes, strict)


def pemohon(skema, data):
    return form.pemohon(skema, data)
