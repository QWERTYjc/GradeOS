"""Coordinate conversion utilities."""

from typing import List
from src.models.region import BoundingBox


def normalize_coordinates(
    box_1000: List[int],
    img_width: int,
    img_height: int,
) -> BoundingBox:
    """Convert normalized coordinates (0-1000) to pixel coordinates."""
    if len(box_1000) != 4:
        raise ValueError(
            f"box_1000 must contain 4 elements, got {len(box_1000)}"
        )

    if img_width <= 0 or img_height <= 0:
        raise ValueError(
            f"Image dimensions must be positive, got width={img_width}, height={img_height}"
        )

    ymin_norm, xmin_norm, ymax_norm, xmax_norm = box_1000

    for coord, name in [
        (ymin_norm, "ymin"),
        (xmin_norm, "xmin"),
        (ymax_norm, "ymax"),
        (xmax_norm, "xmax"),
    ]:
        if not (0 <= coord <= 1000):
            raise ValueError(
                f"{name} must be within 0-1000, got {coord}"
            )

    pixel_ymin = int(ymin_norm * img_height / 1000)
    pixel_xmin = int(xmin_norm * img_width / 1000)
    pixel_ymax = int(ymax_norm * img_height / 1000)
    pixel_xmax = int(xmax_norm * img_width / 1000)

    pixel_ymin = max(0, min(pixel_ymin, img_height))
    pixel_xmin = max(0, min(pixel_xmin, img_width))
    pixel_ymax = max(0, min(pixel_ymax, img_height))
    pixel_xmax = max(0, min(pixel_xmax, img_width))

    return BoundingBox(
        ymin=pixel_ymin,
        xmin=pixel_xmin,
        ymax=pixel_ymax,
        xmax=pixel_xmax,
    )


def denormalize_coordinates(
    box_pixel: BoundingBox,
    img_width: int,
    img_height: int,
) -> List[int]:
    """Convert pixel coordinates to normalized (0-1000) coordinates."""
    if img_width <= 0 or img_height <= 0:
        raise ValueError(
            f"Image dimensions must be positive, got width={img_width}, height={img_height}"
        )

    ymin_norm = int(box_pixel.ymin * 1000 / img_height)
    xmin_norm = int(box_pixel.xmin * 1000 / img_width)
    ymax_norm = int(box_pixel.ymax * 1000 / img_height)
    xmax_norm = int(box_pixel.xmax * 1000 / img_width)

    ymin_norm = max(0, min(ymin_norm, 1000))
    xmin_norm = max(0, min(xmin_norm, 1000))
    ymax_norm = max(0, min(ymax_norm, 1000))
    xmax_norm = max(0, min(xmax_norm, 1000))

    return [ymin_norm, xmin_norm, ymax_norm, xmax_norm]
