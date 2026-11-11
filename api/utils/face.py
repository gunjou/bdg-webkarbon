# api/utils/face.py
import io

import face_recognition
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1024  # perkecil foto besar: deteksi lebih cepat, file lebih kecil


class FaceError(ValueError):
    pass


def process_face_photo(raw):
    """Validasi foto wajah. Kembalikan (jpeg_bytes, embedding 128 float).

    Foto di-encode ulang ke JPEG: buang EXIF/metadata & isi non-gambar yang disisipkan.
    """
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img).convert("RGB")  # putar sesuai orientasi kamera HP
    except (UnidentifiedImageError, OSError):
        raise FaceError("File bukan gambar yang valid")
    img.thumbnail((MAX_SIDE, MAX_SIDE))

    locations = face_recognition.face_locations(np.array(img))
    if not locations:
        raise FaceError("Wajah tidak terdeteksi")
    if len(locations) > 1:
        raise FaceError("Terdeteksi lebih dari 1 wajah")
    embedding = face_recognition.face_encodings(np.array(img), known_face_locations=locations)[0]

    out = io.BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue(), [float(x) for x in embedding]


def face_distance(known, candidate):
    """Jarak euclidean embedding (sama dgn face_recognition.face_distance). Kecil = makin mirip."""
    return float(np.linalg.norm(np.array(known, dtype=float) - np.array(candidate, dtype=float)))
