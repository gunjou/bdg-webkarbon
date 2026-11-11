# api/modules/master/__init__.py
# Modul master: data referensi. Tiap sub-modul punya namespace sendiri (tag Swagger terpisah)
# dan didaftarkan lewat NAMESPACES di bawah. Sub-modul baru: buat folder + tambah 1 baris di sini.
from .hari_libur import ns as hari_libur_ns
from .jabatan import ns as jabatan_ns
from .jadwal_kerja import ns as jadwal_kerja_ns
from .jenis_izin import ns as jenis_izin_ns
from .lokasi_kantor import ns as lokasi_kantor_ns

NAMESPACES = [
    (jabatan_ns, "/master/jabatan"),
    (lokasi_kantor_ns, "/master/lokasi-kantor"),
    (jadwal_kerja_ns, "/master/jadwal-kerja"),
    (jenis_izin_ns, "/master/jenis-izin"),
    (hari_libur_ns, "/master/hari-libur"),
]
