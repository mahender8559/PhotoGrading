from __future__ import annotations

from pathlib import Path
import math
import numpy as np
import cv2
from PIL import Image, ImageOps

from .recipe import validate_recipe, GLOBAL_RANGES

DEFAULTS = {
    "exposure_ev": 0.0, "contrast": 1.0, "brightness": 0.0,
    "highlights": 0.0, "shadows": 0.0, "temperature": 0.0, "tint": 0.0,
    "saturation": 0.0, "vibrance": 0.0, "red_gain": 1.0,
    "green_gain": 1.0, "blue_gain": 1.0, "gamma": 1.0, "sharpen": 0.0,
}


def _apply_adjustments(rgb: np.ndarray, params: dict) -> np.ndarray:
    p = DEFAULTS | params
    x = rgb.astype(np.float32) / 255.0

    if p["exposure_ev"]:
        x *= 2.0 ** p["exposure_ev"]
    if p["contrast"] != 1.0:
        x = (x - 0.5) * p["contrast"] + 0.5
    if p["brightness"]:
        x += p["brightness"]
    if p["highlights"]:
        # Smoothly target upper luminance range.
        lum = x @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        w = np.clip((lum - 0.35) / 0.65, 0, 1) ** 1.5
        x += (p["highlights"] / 100.0) * -0.35 * w[..., None]
    if p["shadows"]:
        lum = x @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        w = np.clip((0.65 - lum) / 0.65, 0, 1) ** 1.5
        x += (p["shadows"] / 100.0) * 0.35 * w[..., None]

    # Temperature/tint as controlled channel gains on display RGB.
    t = p["temperature"] / 100.0
    ti = p["tint"] / 100.0
    gains = np.array([
        p["red_gain"] * (1 + 0.15*t + 0.06*ti),
        p["green_gain"] * (1 - 0.12*ti),
        p["blue_gain"] * (1 - 0.15*t + 0.06*ti),
    ], np.float32)
    x *= gains

    if p["gamma"] != 1.0:
        x = np.clip(x, 0, 1) ** (1.0 / p["gamma"])

    if p["saturation"] or p["vibrance"]:
        hsv = cv2.cvtColor(np.clip(x, 0, 1), cv2.COLOR_RGB2HSV)
        sat = hsv[..., 1]
        sat *= 1.0 + p["saturation"] / 100.0
        if p["vibrance"]:
            sat += (p["vibrance"] / 100.0) * (1.0 - np.clip(sat, 0, 1)) * 0.65
        hsv[..., 1] = np.clip(sat, 0, 1)
        x = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

    if p["sharpen"] > 0:
        blur = cv2.GaussianBlur(x, (0, 0), 1.0)
        x = x + p["sharpen"] * (x - blur)

    return np.clip(x * 255.0, 0, 255)


def _curve_lut(points: list) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float32)
    return np.interp(np.arange(256), pts[:, 0], pts[:, 1]).astype(np.uint8)


def _apply_curves(rgb: np.ndarray, curves: dict) -> np.ndarray:
    out = np.clip(rgb, 0, 255).astype(np.uint8)
    if "master" in curves:
        out = cv2.LUT(out, _curve_lut(curves["master"]))
    for idx, channel in enumerate(("red", "green", "blue")):
        if channel in curves:
            lut = _curve_lut(curves[channel])
            out[..., idx] = lut[out[..., idx]]
    return out.astype(np.float32)


def _apply_hsl(rgb: np.ndarray, hsl: dict) -> np.ndarray:
    if not hsl:
        return rgb
    hsv = cv2.cvtColor(np.clip(rgb / 255.0, 0, 1), cv2.COLOR_RGB2HSV)
    # OpenCV float HSV hue is 0..360, saturation/value 0..1.
    hue, sat, val = cv2.split(hsv)
    names = ["red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta"]
    centers = [0, 25, 55, 120, 180, 220, 270, 315]
    for name, center in zip(names, centers):
        cfg = hsl.get(name, {})
        if not cfg:
            continue
        distance = np.minimum(np.abs(hue - center), 360 - np.abs(hue - center))
        weight = np.clip(1.0 - distance / 35.0, 0, 1)
        sat = np.clip(sat * (1 + cfg.get("saturation", 0) / 100.0 * weight), 0, 1)
        val = np.clip(val + cfg.get("luminance", 0) / 100.0 * 0.35 * weight, 0, 1)
        hue = (hue + cfg.get("hue", 0) * weight) % 360
    return cv2.cvtColor(cv2.merge([hue, sat, val]), cv2.COLOR_HSV2RGB) * 255.0


def _make_region_mask(region: dict, shape: tuple[int, int], recipe_dir: Path) -> np.ndarray:
    h, w = shape
    mask = np.zeros((h, w), dtype=np.uint8)
    if "rectangle" in region:
        x, y, rw, rh = [int(round(v)) for v in region["rectangle"]]
        x0, y0, x1, y1 = max(0, x), max(0, y), min(w, x+rw), min(h, y+rh)
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = 255
    elif "polygon" in region:
        pts = np.asarray(region["polygon"], dtype=np.float32).round().astype(np.int32)
        cv2.fillPoly(mask, [pts], 255)
    else:
        mask_path = Path(region["mask"])
        if not mask_path.is_absolute():
            mask_path = recipe_dir / mask_path
        loaded = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if loaded is None:
            raise FileNotFoundError(f"Could not load region mask: {mask_path}")
        if loaded.shape != (h, w):
            loaded = cv2.resize(loaded, (w, h), interpolation=cv2.INTER_LINEAR)
        mask = loaded

    feather = float(region.get("feather", 0))
    if feather > 0:
        sigma = max(feather / 3.0, 0.1)
        mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=sigma, sigmaY=sigma)
    return mask.astype(np.float32)[..., None] / 255.0


def _apply_effects(rgb: np.ndarray, params: dict) -> np.ndarray:
    out = rgb.astype(np.float32)
    vignette = float(params.get("vignette", 0))
    if vignette:
        h, w = out.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        nx = (xx - (w-1)/2) / max(w/2, 1)
        ny = (yy - (h-1)/2) / max(h/2, 1)
        radius = np.sqrt(nx*nx + ny*ny)
        factor = 1.0 - vignette * np.clip((radius - 0.25) / 0.9, 0, 1) ** 1.5 * 0.65
        out *= factor[..., None]
    grain = float(params.get("grain", 0))
    if grain:
        rng = np.random.default_rng(0)  # reproducible recipe output
        noise = rng.normal(0, grain * 10.0, out.shape[:2]).astype(np.float32)
        out += noise[..., None]
    return np.clip(out, 0, 255)


def process_array(image: np.ndarray, recipe: dict, recipe_dir: str | Path = ".") -> np.ndarray:
    validate_recipe({k: v for k, v in recipe.items() if not k.startswith("_")})
    recipe_dir = Path(recipe.get("_recipe_dir", recipe_dir))
    out = image.astype(np.float32)
    global_params = recipe.get("global", {})
    if global_params:
        out = _apply_adjustments(out, global_params)
    if recipe.get("curves"):
        out = _apply_curves(out, recipe["curves"])
    if recipe.get("hsl"):
        out = _apply_hsl(out, recipe["hsl"])
    if recipe.get("global", {}).get("vignette") or recipe.get("global", {}).get("grain"):
        out = _apply_effects(out, recipe["global"])

    h, w = out.shape[:2]
    for region in recipe.get("regions", []):
        mask = _make_region_mask(region, (h, w), recipe_dir)
        adjusted = _apply_adjustments(out, region.get("adjustments", {}))
        out = out * (1.0 - mask) + adjusted * mask
    return np.clip(out, 0, 255).astype(np.uint8)


def load_image(path: str | Path) -> Image.Image:
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGB")
    if image.mode == "RGBA":
        # Keep alpha separate for safe RGB-only grading, then recombine.
        return image
    return image


def process_file(input_path: str | Path, recipe: dict, output_dir: str | Path) -> Path:
    input_path, output_dir = Path(input_path), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image = load_image(input_path)
    alpha = image.getchannel("A") if image.mode == "RGBA" else None
    rgb_image = image.convert("RGB")
    arr = np.asarray(rgb_image, dtype=np.uint8)
    result = process_array(arr, recipe)
    output_cfg = recipe.get("output", {})
    fmt = output_cfg.get("format", "preserve").lower()
    if fmt == "preserve":
        fmt = image.format.lower() if image.format else "jpeg"
    if fmt == "jpg":
        fmt = "jpeg"
    pil_format = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}.get(fmt, "JPEG")
    result_img = Image.fromarray(result, "RGB")
    if alpha is not None and pil_format in {"PNG", "WEBP"}:
        result_img.putalpha(alpha)
    max_w, max_h = output_cfg.get("max_width"), output_cfg.get("max_height")
    if max_w or max_h:
        result_img.thumbnail((max_w or result_img.width, max_h or result_img.height), Image.Resampling.LANCZOS)
    suffix = output_cfg.get("suffix", "_graded")
    output_path = output_dir / f"{input_path.stem}{suffix}.{fmt}"
    save_kwargs = {}
    if pil_format in {"JPEG", "WEBP"}:
        save_kwargs["quality"] = output_cfg.get("quality", 95)
    result_img.save(output_path, format=pil_format, **save_kwargs)
    return output_path
