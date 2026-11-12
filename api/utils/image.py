# api/utils/image.py
import io

from PIL import Image, ImageOps


def compress_jpeg(data, max_bytes, min_side=64):
    """Kecilkan JPEG sampai <= max_bytes: turunkan kualitas dulu, lalu perkecil dimensi 25% dan ulangi."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")  # putar sesuai kamera HP
    while True:
        for quality in (85, 75, 65, 55, 45, 35):
            out = io.BytesIO()
            img.save(out, "JPEG", quality=quality, optimize=True)
            if out.tell() <= max_bytes:
                return out.getvalue()
        if min(img.size) <= min_side:
            return out.getvalue()  # sudah sangat kecil, terima apa adanya
        img = img.resize((int(img.width * 0.75), int(img.height * 0.75)), Image.LANCZOS)
