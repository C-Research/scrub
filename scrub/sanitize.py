import io
from pathlib import Path

from PIL import Image


def reencode_png(raw_rgb_bytes: bytes, width: int, height: int) -> bytes:
    img = Image.frombuffer("RGB", (width, height), raw_rgb_bytes, "raw", "RGB", 0, 1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def process_image_file(path: Path) -> bytes:
    with Image.open(path) as img:
        img = img.convert("RGB")
        w, h = img.size
        raw = img.tobytes()
    return reencode_png(raw, w, h)
