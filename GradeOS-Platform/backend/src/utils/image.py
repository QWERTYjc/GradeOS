"""Image conversion helpers."""

from io import BytesIO
from typing import Optional

from PIL import Image


def pil_to_jpeg_bytes(image: Image.Image, quality: int = 85) -> bytes:
    """Convert a PIL Image to JPEG bytes."""
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def to_jpeg_bytes(raw_bytes: bytes, quality: int = 85) -> bytes:
    """Convert raw image bytes to JPEG bytes when possible."""
    try:
        image = Image.open(BytesIO(raw_bytes))
        return pil_to_jpeg_bytes(image, quality=quality)
    except Exception:
        # Fall back to the original bytes if conversion fails.
        return raw_bytes
