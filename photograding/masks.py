from __future__ import annotations

import cv2
import numpy as np


def canvas_image_to_mask(
    image_data: np.ndarray,
    output_size: tuple[int, int],
) -> np.ndarray:
    """Convert drawable-canvas RGB/RGBA output to a grayscale uint8 mask.

    White canvas pixels mean full effect, black means no effect. The returned
    mask is resized to the requested width and height.
    """
    data = np.asarray(image_data)
    if data.ndim != 3 or data.shape[2] not in (3, 4):
        raise ValueError("Canvas image data must be an RGB or RGBA array")
    if data.shape[0] < 1 or data.shape[1] < 1:
        raise ValueError("Canvas image data is empty")

    rgb = np.clip(data[..., :3], 0, 255).astype(np.uint8)
    grayscale = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    if data.shape[2] == 4:
        alpha = np.clip(data[..., 3], 0, 255).astype(np.uint8)
        grayscale = (
            grayscale.astype(np.float32) * (alpha.astype(np.float32) / 255.0)
        ).round().astype(np.uint8)

    width, height = output_size
    if width < 1 or height < 1:
        raise ValueError("Output mask dimensions must be positive")
    if grayscale.shape != (height, width):
        grayscale = cv2.resize(
            grayscale,
            (width, height),
            interpolation=cv2.INTER_LINEAR,
        )
    return grayscale.astype(np.uint8)
