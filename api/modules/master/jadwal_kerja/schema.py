# api/modules/master/jadwal_kerja/schema.py
from flask_restx import fields

from api.shared.docs import audit_fields
from . import ns

_CONTOH = {
    "senin": {"masuk": "07:30", "pulang": "15:30"},
    "selasa": {"masuk": "07:30", "pulang": "15:30"},
    "rabu": {"masuk": "07:30", "pulang": "15:30"},
    "kamis": {"masuk": "07:30", "pulang": "15:30"},
    "jumat": {"masuk": "07:30", "pulang": "11:30"},
    "sabtu": None,
    "minggu": None,
}

# isi jadwal_harian divalidasi di service (hari, format HH:MM, masuk < pulang)
jadwal_kerja_input = ns.model("JadwalKerjaInput", {
    "name": fields.String(required=True, min_length=1, max_length=100, example="Jadwal Normal"),
    "jadwal_harian": fields.Raw(required=True, example=_CONTOH,
                                description="Per hari: {masuk, pulang} format HH:MM, atau null = libur. "
                                            "Hari yang tidak diisi dianggap libur."),
    "toleransi_terlambat_menit": fields.Integer(default=0, min=0, example=15),
})

jadwal_kerja_out = ns.model("JadwalKerja", {
    "id_jadwal_kerja": fields.Integer(example=1),
    "name": fields.String(example="Jadwal Normal"),
    "jadwal_harian": fields.Raw(example=_CONTOH, description="7 hari lengkap; null = libur"),
    "toleransi_terlambat_menit": fields.Integer(example=15),
    **audit_fields(),
})
