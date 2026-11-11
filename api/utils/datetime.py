# api/utils/datetime.py
from datetime import datetime
from zoneinfo import ZoneInfo

WITA = ZoneInfo("Asia/Makassar")


def get_wita():
    """Waktu sekarang di WITA, dengan tzinfo (aware).
    Tetap aware: kolom TIMESTAMPTZ menafsirkan datetime naive memakai zona sesi DB, jadi bisa bergeser 8 jam."""
    return datetime.now(WITA)
