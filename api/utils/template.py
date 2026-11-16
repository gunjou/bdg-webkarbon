# api/utils/template.py
"""Template surat: Jinja sandbox, sanitasi HTML, helper tanggal & terbilang. Fungsi murni (tanpa DB/Flask)."""
from datetime import date

import nh3
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

ALLOWED_TAGS = {"p", "b", "strong", "i", "em", "u", "br", "table", "tbody", "tr", "td", "th",
                "ul", "ol", "li", "span"}
ALLOWED_ATTRS = {"p": {"style"}, "span": {"style"}, "td": {"style", "colspan", "rowspan"},
                 "th": {"style", "colspan", "rowspan"}, "table": {"style"}}
# hanya properti tata letak; url()/background dibuang supaya PDF tidak mengambil resource luar
ALLOWED_STYLES = {"text-align", "font-weight", "font-style", "text-decoration", "width", "text-indent"}

BULAN = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
         "November", "Desember")
_SATUAN = ("", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas")


def sanitize_html(html):
    return nh3.clean(html or "", tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS,
                     filter_style_properties=ALLOWED_STYLES, url_schemes=set())


def tgl_indo(value):
    """date / 'YYYY-MM-DD' -> '3 November 1998'. Kosong -> ''."""
    if not value:
        return ""
    d = value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def _terbilang(n):
    if n < 12:
        return _SATUAN[n]
    if n < 20:
        return _terbilang(n - 10) + " belas"
    if n < 100:
        return (_terbilang(n // 10) + " puluh " + _terbilang(n % 10)).strip()
    if n < 200:
        return ("seratus " + _terbilang(n - 100)).strip()
    if n < 1000:
        return (_terbilang(n // 100) + " ratus " + _terbilang(n % 100)).strip()
    if n < 2000:
        return ("seribu " + _terbilang(n - 1000)).strip()
    for besar, nama in ((10 ** 12, "triliun"), (10 ** 9, "miliar"), (10 ** 6, "juta"), (1000, "ribu")):
        if n >= besar:
            return (_terbilang(n // besar) + f" {nama} " + _terbilang(n % besar)).strip()


def terbilang(value, satuan=""):
    """50000000 -> 'lima puluh juta'; satuan='rupiah' -> 'lima puluh juta rupiah'. Pecahan dibuang."""
    n = int(float(str(value or 0).replace(".", "").replace(",", ".")) if isinstance(value, str) else value or 0)
    teks = "nol" if n == 0 else _terbilang(abs(n))
    teks = ("minus " if n < 0 else "") + teks
    return f"{teks} {satuan}".strip()


def make_env(helpers=None):
    """Sandbox Jinja (template dari user rentan SSTI). helpers = {nama: fungsi} tambahan (biodata, tabel, label).
    Fungsi ikut didaftarkan sebagai filter agar bisa dipakai `{{ x | tgl_indo }}` maupun `{{ tgl_indo(x) }}`."""
    env = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)
    fns = {"tgl_indo": tgl_indo, "terbilang": terbilang, **(helpers or {})}
    env.globals.update(fns)
    env.filters.update(fns)
    return env
