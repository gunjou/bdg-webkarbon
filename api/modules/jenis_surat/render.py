# api/modules/jenis_surat/render.py
"""Render surat: redaksi (template user, SANDBOX) + layout (kop, judul, nomor, tanda tangan; template kode) -> HTML -> PDF.
Fungsi murni: semua data (settings, label ref_options, logo, penandatangan) dioper dari service, tanpa DB.

Bentuk `data` (surat.data):
  - section penduduk   : data[key] = {nama, nik, no_kk, tempat_lahir, tanggal_lahir, jenis_kelamin (L/P), agama,
                         pekerjaan, status_perkawinan, kewarganegaraan, dusun (code ref_options), rt, rw, alamat}
  - section fields     : data[field_key] = nilai (date 'YYYY-MM-DD', rupiah angka, select = code/opsi)
  - section daftar     : data[key] = [{kolom: nilai}, ...]
  - section teks_bebas : data[key] = HTML (dibersihkan saat render)
Key yang tidak ada di data dirender kosong."""
import base64
from pathlib import Path
from urllib.parse import unquote, urlparse

from jinja2 import Environment
from markupsafe import Markup, escape

from api.utils.template import make_env, sanitize_html, tgl_indo

KERTAS = {"F4": "215mm 330mm", "A4": "A4"}
JENIS_KELAMIN = {"L": "Laki-laki", "P": "Perempuan"}
REF_GROUP = {"agama": "AGAMA", "pekerjaan": "PEKERJAAN", "status_perkawinan": "STATUS_PERKAWINAN",
             "kewarganegaraan": "KEWARGANEGARAAN", "dusun": "DUSUN"}


class Rupiah(int):
    """Tampil 'Rp 50.000.000', tetap angka untuk terbilang()."""
    def __str__(self):
        return "Rp " + f"{int(self):,}".replace(",", ".")

    __html__ = __str__


class Orang(dict):
    tampilkan = ()


class Daftar(list):
    columns = ()


def _rupiah(v):
    try:
        return Rupiah(int(float(v)))
    except (TypeError, ValueError):
        return ""


def _nilai(field, v, labels):
    if v in (None, ""):
        return ""
    if field["type"] == "rupiah":
        return _rupiah(v)
    if field["type"] == "select" and field.get("options_group"):
        return labels.get(field["options_group"], {}).get(v, v)
    return v


def _alamat(p, labels, desa):
    bagian = []
    if p.get("alamat"):
        bagian.append(p["alamat"])
    if p.get("dusun"):
        bagian.append("Dusun " + labels.get("DUSUN", {}).get(p["dusun"], p["dusun"]))
    if p.get("rt"):
        bagian.append(f"RT {p['rt']}" + (f"/RW {p['rw']}" if p.get("rw") else ""))
    bagian += [f"Desa {desa['nama']}", f"Kecamatan {desa['kecamatan']}", f"Kabupaten {desa['kabupaten']}"]
    return ", ".join(bagian)


def _orang(p, tampilkan, labels, desa):
    p = p or {}
    o = Orang({k: p.get(k) or "" for k in ("nama", "nik", "no_kk", "tempat_lahir", "rt", "rw")})
    for k, g in REF_GROUP.items():
        o[k] = labels.get(g, {}).get(p.get(k), p.get(k) or "")
    o["tanggal_lahir"] = tgl_indo(p.get("tanggal_lahir"))
    o["ttl"] = ", ".join(x for x in (o["tempat_lahir"], o["tanggal_lahir"]) if x)
    o["jenis_kelamin"] = JENIS_KELAMIN.get(p.get("jenis_kelamin"), "")
    o["alamat"] = _alamat(p, labels, desa)
    o.tampilkan = tampilkan
    return o


def build_context(skema, data, labels, desa):
    from .service import BIODATA  # hindari import melingkar
    data, ctx = data or {}, {"desa": desa}
    for s in skema["sections"]:
        if s["type"] == "penduduk":
            ctx[s["key"]] = _orang(data.get(s["key"]), [(k, BIODATA[k]) for k in s["tampilkan"]], labels, desa)
        elif s["type"] == "fields":
            for f in s["fields"]:
                ctx[f["key"]] = _nilai(f, data.get(f["key"]), labels)
        elif s["type"] == "daftar":
            rows = Daftar({c["key"]: _nilai(c, (r or {}).get(c["key"]), labels) for c in s["columns"]}
                          for r in (data.get(s["key"]) or []))
            rows.columns = s["columns"]
            ctx[s["key"]] = rows
        else:
            ctx[s["key"]] = Markup(sanitize_html(data.get(s["key"]) or ""))
    return ctx


def _biodata(orang):
    if not isinstance(orang, Orang):
        return ""
    rows = "".join(f'<tr><td class="bl">{escape(label)}</td><td class="bt">:</td><td>{escape(orang[k] or "-")}</td></tr>'
                   for k, label in orang.tampilkan)
    return Markup(f'<table class="biodata">{rows}</table>')


def _tabel(daftar):
    if not isinstance(daftar, Daftar):
        return ""
    head = "<th>No</th>" + "".join(f"<th>{escape(c['label'])}</th>" for c in daftar.columns)
    body = "".join(
        f"<tr><td>{i}</td>" + "".join(
            f"<td>{escape(tgl_indo(r[c['key']]) if c['type'] == 'date' else r[c['key']])}</td>" for c in daftar.columns
        ) + "</tr>"
        for i, r in enumerate(daftar, 1))
    return Markup(f'<table class="daftar"><tr>{head}</tr>{body}</table>')


def render_isi(redaksi, skema, data, labels, desa):
    """Redaksi -> HTML isi. Template user selalu lewat sandbox."""
    semua = {c: l for g in labels.values() for c, l in g.items()}
    env = make_env({"biodata": _biodata, "tabel": _tabel, "label": lambda kode: semua.get(kode, kode or "")})
    return Markup(env.from_string(redaksi).render(build_context(skema, data, labels, desa)))


ASSETS = Path(__file__).resolve().parents[2] / "assets"
LOGO_KAB = ASSETS / "logo-kabupaten.svg"
LOGO_DESA = ASSETS / "logo-desa.png"
FONTS = ASSETS / "fonts"
# font dibundel (Liberation Serif, metrik sama dengan Times New Roman) agar tampilan sama di dev & server
FONT_FACE = "".join(
    f'@font-face {{ font-family: "Surat Serif"; src: url("{(FONTS / f).as_uri()}"); '
    f'font-weight: {w}; font-style: {st}; }}\n'
    for f, w, st in (("LiberationSerif-Regular.ttf", "normal", "normal"), ("LiberationSerif-Bold.ttf", "bold", "normal"),
                     ("LiberationSerif-Italic.ttf", "normal", "italic"), ("LiberationSerif-BoldItalic.ttf", "bold", "italic")))

LAYOUT = Environment(autoescape=True).from_string("""<!doctype html>
<html><head><meta charset="utf-8"><style>
{{ font_face }}
@page { size: {{ kertas }}; margin: 12mm 20mm 20mm 25mm; }
body { font-family: "Surat Serif", serif; font-size: 12pt; line-height: 1.5; color: #000; }
.kop { width: 100%; border-collapse: collapse; border-bottom: 3px solid #000; margin-bottom: 2px; }
.kop-garis { border-bottom: 1px solid #000; margin-bottom: 14px; }
.kop td { vertical-align: middle; text-align: center; padding: 0 0 4px; line-height: 1.15; }
.kop .logo { width: 26mm; text-align: left; } .kop .logo img { width: 22mm; max-height: 26mm; }
.kop .logo.kanan { text-align: right; }
.kop .kab { font-size: 14pt; }
.kop .desa { font-size: 18pt; letter-spacing: 1px; }
.kop .info { font-size: 9pt; }  /* setara text-xs pratinjau Pengaturan; alamat muat 1 baris */
.judul { text-align: center; font-weight: bold; text-transform: uppercase; margin: 0; }
/* garis judul pakai border agar ada jarak dari huruf (underline bawaan terlalu mepet) */
.judul span { display: inline-block; border-bottom: 1px solid #000; padding-bottom: 2px; line-height: 1.2; }
.nomor { text-align: center; margin: 0 0 18px; }
.isi p { text-align: justify; text-indent: 12mm; margin: 0 0 10px; }
.biodata { margin: 4px 0 12px 12mm; border-collapse: collapse; }
.biodata td { padding: 0 4px; vertical-align: top; }
.biodata .bl { width: 46mm; } .biodata .bt { width: 4mm; }
.daftar { width: 100%; border-collapse: collapse; margin: 4px 0 12px; }
.daftar td, .daftar th { border: 1px solid #000; padding: 1px 5px; }
.ttd { margin: 20px 0 0 55%; text-align: center; line-height: 1.3; page-break-inside: avoid; }
.ttd .nama { margin-top: 72px; font-weight: bold; text-transform: uppercase; }
.watermark { position: fixed; top: 38%; left: 0; width: 100%; text-align: center; font-size: 110pt; font-weight: bold;
             color: rgba(200, 0, 0, 0.13); transform: rotate(-35deg); z-index: -1; }
</style></head><body>
{% if watermark %}<div class="watermark" style="font-size: {{ 110 if watermark|length <= 6 else 64 }}pt">{{ watermark }}</div>{% endif %}
<table class="kop"><tr>
  <td class="logo"><img src="{{ logo_kab }}"></td>
  <td>
    <div class="kab">PEMERINTAH KABUPATEN {{ desa.kabupaten | upper }}</div>
    <div class="kab">KECAMATAN {{ desa.kecamatan | upper }}</div>
    <div class="desa">DESA {{ desa.nama | upper }}</div>
    {% if desa.alamat %}<div class="info">{{ desa.alamat }}</div>{% endif %}
    {% if desa.website or desa.email %}<div class="info">
      {%- if desa.website %}Website: {{ desa.website }}{% endif %}{% if desa.website and desa.email %} &nbsp; {% endif %}
      {%- if desa.email %}E-mail: {{ desa.email }}{% endif %}</div>{% endif %}
  </td>
  <td class="logo kanan"><img src="{{ logo }}"></td>
</tr></table>
<div class="kop-garis"></div>
<p class="judul"><span>{{ judul }}</span></p>
<p class="nomor">Nomor : {{ nomor or "......................................" }}</p>
<div class="isi">{{ isi }}</div>
<div class="ttd">
  <div>{{ desa.nama }}, {{ tanggal or "...................." }}</div>
  {% if ttd.atas_nama %}<div>a.n Kepala Desa {{ desa.nama }}</div><div>{{ ttd.jabatan }}</div>
  {% else %}<div>Kepala Desa {{ desa.nama }}</div>{% endif %}
  <div class="nama">{{ ttd.nama or "...................................." }}</div>
  {% if ttd.nip %}<div>NIP. {{ ttd.nip }}</div>{% endif %}
</div>
</body></html>""")


def logo_uri(data=None):
    """Logo desa (kanan kop): upload (PNG) bila ada, selain itu logo desa bawaan."""
    return "data:image/png;base64," + base64.b64encode(data or LOGO_DESA.read_bytes()).decode()


def logo_kiri_uri(data=None):
    """Logo kiri kop: upload (PNG) bila ada, selain itu logo kabupaten bawaan (SVG)."""
    if data:
        return "data:image/png;base64," + base64.b64encode(data).decode()
    return "data:image/svg+xml;base64," + base64.b64encode(LOGO_KAB.read_bytes()).decode()


def render_html(*, judul, redaksi, skema, data, labels, settings, logo=None, logo_kiri=None, nomor=None, tanggal=None,
                penandatangan=None, watermark=None):
    """logo = bytes PNG logo desa upload atau None (pakai logo desa bawaan); logo_kiri sama, bawaan logo kabupaten; penandatangan = {nama, jabatan, nip, atas_nama};
    tanggal = date/ISO; watermark mis. 'DRAF' / 'DIBATALKAN'."""
    desa = {k: settings.get(f"desa.{k}") or "" for k in ("nama", "kecamatan", "kabupaten", "alamat", "email", "website")}
    return LAYOUT.render(
        kertas=KERTAS.get(settings.get("surat.ukuran_kertas"), KERTAS["F4"]),
        font_face=Markup(FONT_FACE), desa=desa, judul=judul, nomor=nomor, tanggal=tgl_indo(tanggal), ttd=penandatangan or {},
        watermark=watermark, isi=render_isi(redaksi, skema, data, labels, desa), logo=logo_uri(logo), logo_kab=logo_kiri_uri(logo_kiri),
    )


def _fetcher():
    """Hanya data: URI dan file font bawaan yang boleh dimuat (cegah SSRF / baca file lewat redaksi)."""
    from weasyprint.urls import URLFetcher

    class _Fetcher(URLFetcher):
        def fetch(self, url, headers=None):
            if url.startswith("file:"):
                path = Path(unquote(urlparse(url).path)).resolve()  # resolve: tolak ../ keluar folder font
                if path.parent != FONTS.resolve():
                    raise ValueError(f"URL tidak diizinkan: {url}")
            return super().fetch(url, headers)

    return _Fetcher(allowed_protocols={"data", "file"})


def to_pdf(html):
    """HTML -> PDF bytes."""
    from weasyprint import HTML  # impor lambat: butuh pango; app tetap jalan tanpa fitur PDF
    return HTML(string=html, url_fetcher=_fetcher()).write_pdf()
