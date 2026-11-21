from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GLOBAL_RANGES = {
    "exposure_ev": (-5.0, 5.0), "contrast": (0.0, 3.0),
    "brightness": (-1.0, 1.0), "highlights": (-100.0, 100.0),
    "shadows": (-100.0, 100.0), "temperature": (-100.0, 100.0),
    "tint": (-100.0, 100.0), "saturation": (-100.0, 100.0),
    "vibrance": (-100.0, 100.0), "red_gain": (0.0, 3.0),
    "green_gain": (0.0, 3.0), "blue_gain": (0.0, 3.0),
    "gamma": (0.1, 4.0), "vignette": (0.0, 1.0),
    "grain": (0.0, 1.0), "sharpen": (0.0, 2.0),
}
LOCAL_KEYS = {k for k in GLOBAL_RANGES if k not in {"vignette", "grain"}}
HSL_COLOURS = {"red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta"}


class RecipeError(ValueError):
    pass


def _check_adjustments(adjustments: Any, allowed: set[str], label: str) -> None:
    if not isinstance(adjustments, dict):
        raise RecipeError(f"{label} must be an object")
    unknown = set(adjustments) - allowed
    if unknown:
        raise RecipeError(f"Unknown {label} parameter(s): {', '.join(sorted(unknown))}")
    for key, value in adjustments.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RecipeError(f"{label}.{key} must be numeric")
        lo, hi = GLOBAL_RANGES[key]
        if not lo <= float(value) <= hi:
            raise RecipeError(f"{label}.{key} must be between {lo} and {hi}")


def validate_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(recipe, dict):
        raise RecipeError("Recipe root must be a JSON object")
    allowed_top = {"version", "global", "curves", "hsl", "regions", "output"}
    unknown = set(recipe) - allowed_top
    if unknown:
        raise RecipeError(f"Unknown top-level key(s): {', '.join(sorted(unknown))}")
    if recipe.get("version", 1) != 1:
        raise RecipeError("Only recipe version 1 is supported")

    _check_adjustments(recipe.get("global", {}), set(GLOBAL_RANGES), "global")

    curves = recipe.get("curves", {})
    if not isinstance(curves, dict) or set(curves) - {"master", "red", "green", "blue"}:
        raise RecipeError("curves must contain only master/red/green/blue")
    for channel, points in curves.items():
        if not isinstance(points, list) or len(points) < 2:
            raise RecipeError(f"curves.{channel} needs at least two points")
        last_x = -1
        for point in points:
            if (not isinstance(point, list) or len(point) != 2 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 255 for v in point)):
                raise RecipeError(f"Invalid control point in curves.{channel}")
            if point[0] <= last_x:
                raise RecipeError(f"Input values in curves.{channel} must increase strictly")
            last_x = point[0]

    hsl = recipe.get("hsl", {})
    if not isinstance(hsl, dict) or set(hsl) - HSL_COLOURS:
        raise RecipeError("hsl contains an unsupported colour name")
    for colour, values in hsl.items():
        if not isinstance(values, dict) or set(values) - {"hue", "saturation", "luminance"}:
            raise RecipeError(f"Invalid HSL settings for {colour}")
        for key, value in values.items():
            lo, hi = (-180, 180) if key == "hue" else (-100, 100)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
                raise RecipeError(f"hsl.{colour}.{key} must be between {lo} and {hi}")

    regions = recipe.get("regions", [])
    if not isinstance(regions, list):
        raise RecipeError("regions must be a list")
    for i, region in enumerate(regions):
        if not isinstance(region, dict):
            raise RecipeError(f"regions[{i}] must be an object")
        selectors = [k for k in ("rectangle", "polygon", "mask") if k in region]
        if len(selectors) != 1:
            raise RecipeError(f"regions[{i}] must contain exactly one of rectangle, polygon or mask")
        if set(region) - {"name", "rectangle", "polygon", "mask", "feather", "adjustments"}:
            raise RecipeError(f"Unknown key in regions[{i}]")
        if "rectangle" in region:
            r = region["rectangle"]
            if not isinstance(r, list) or len(r) != 4 or any(not isinstance(v, (int, float)) for v in r) or r[2] <= 0 or r[3] <= 0:
                raise RecipeError(f"regions[{i}].rectangle must be [x,y,width,height]")
        if "polygon" in region:
            p = region["polygon"]
            if not isinstance(p, list) or len(p) < 3 or any(not isinstance(pt, list) or len(pt) != 2 for pt in p):
                raise RecipeError(f"regions[{i}].polygon needs at least three [x,y] points")
        if "mask" in region and not isinstance(region["mask"], str):
            raise RecipeError(f"regions[{i}].mask must be a path string")
        feather = region.get("feather", 0)
        if isinstance(feather, bool) or not isinstance(feather, (int, float)) or not 0 <= feather <= 200:
            raise RecipeError(f"regions[{i}].feather must be between 0 and 200")
        _check_adjustments(region.get("adjustments", {}), LOCAL_KEYS, f"regions[{i}].adjustments")

    output = recipe.get("output", {})
    if not isinstance(output, dict) or set(output) - {"format", "quality", "suffix", "max_width", "max_height"}:
        raise RecipeError("Invalid output configuration")
    if output.get("format", "preserve").lower() not in {"preserve", "jpeg", "jpg", "png", "webp"}:
        raise RecipeError("output.format must be preserve/jpeg/png/webp")
    quality = output.get("quality", 95)
    if isinstance(quality, bool) or not isinstance(quality, int) or not 1 <= quality <= 100:
        raise RecipeError("output.quality must be an integer from 1 to 100")
    for key in ("max_width", "max_height"):
        val = output.get(key)
        if val is not None and (not isinstance(val, int) or val <= 0):
            raise RecipeError(f"output.{key} must be a positive integer or null")
    return recipe


def load_recipe(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecipeError(f"Invalid JSON: {exc}") from exc
    validate_recipe(data)
    data["_recipe_dir"] = str(path.resolve().parent)
    return data
