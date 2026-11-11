# api/core/storage.py
import logging
import os
import uuid

from api.core import config

log = logging.getLogger(__name__)


def save_file(data, subdir, ext):
    """Simpan bytes ke UPLOAD_DIR/<subdir>/<uuid>.<ext>; kembalikan path relatif (disimpan di DB)."""
    rel = f"{subdir}/{uuid.uuid4().hex}.{ext}"
    full = os.path.join(config.UPLOAD_DIR, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.write(data)
    return rel


def full_path(rel):
    """Path absolut dari path relatif; None jika keluar dari UPLOAD_DIR (cegah path traversal)."""
    full = os.path.abspath(os.path.join(config.UPLOAD_DIR, rel))
    return full if full.startswith(config.UPLOAD_DIR + os.sep) else None


def delete_file(rel):
    """Hapus file; gagal hanya dicatat ke log (file yatim tidak merusak data)."""
    full = rel and full_path(rel)
    if full and os.path.exists(full):
        try:
            os.remove(full)
        except OSError:
            log.exception("Gagal hapus file %s", rel)
