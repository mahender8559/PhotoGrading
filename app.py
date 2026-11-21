from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import time
import zipfile

import numpy as np
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

from photograding.masks import canvas_image_to_mask
from photograding.processor import load_image, process_array
from photograding.recipe import RecipeError, validate_recipe


DATA_DIR = Path(os.environ.get("PHOTOGRADING_DATA_DIR", "data")).expanduser()
SAVED_RECIPES_DIR = DATA_DIR / "recipes"
MASKS_DIR = DATA_DIR / "masks"
SAVED_RECIPES_DIR.mkdir(parents=True, exist_ok=True)
MASKS_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="PhotoGrading", page_icon="🎨", layout="wide")
st.title("PhotoGrading")
st.caption(
    "Deterministic, layer-based photo editing. You control every adjustment and mask; "
    "there is no AI analysis or generative image editing."
)


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-_")
    return value[:48] or "layer"


def resolve_mask_path(mask_value: str, recipe_dir: Path) -> Path:
    path = Path(mask_value).expanduser()
    return path if path.is_absolute() else (recipe_dir / path).resolve()


def package_recipe(recipe: dict, recipe_dir: Path, prefix: str = "masks") -> bytes:
    """Create a portable ZIP containing a recipe and every mask it references."""
    portable = deepcopy({key: value for key, value in recipe.items() if not key.startswith("_")})
    assets: dict[str, bytes] = {}
    for index, region in enumerate(portable.get("regions", []), start=1):
        if "mask" not in region:
            continue
        source = resolve_mask_path(region["mask"], recipe_dir)
        if not source.is_file():
            raise FileNotFoundError(f"Mask file not found: {source}")
        with Image.open(source) as opened:
            buffer = BytesIO()
            opened.convert("L").save(buffer, format="PNG")
        asset_name = f"{prefix}/region_{index:03d}.png"
        assets[asset_name] = buffer.getvalue()
        region["mask"] = asset_name

    archive = BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("photo_recipe.json", json.dumps(portable, indent=2).encode("utf-8"))
        for asset_name, asset_bytes in assets.items():
            zipped.writestr(asset_name, asset_bytes)
    return archive.getvalue()


def save_preset(recipe: dict, recipe_dir: Path, preset_name: str) -> Path:
    slug = slugify(preset_name)
    portable = deepcopy({key: value for key, value in recipe.items() if not key.startswith("_")})
    asset_dir_name = f"{slug}_masks"
    asset_dir = SAVED_RECIPES_DIR / asset_dir_name
    asset_dir.mkdir(parents=True, exist_ok=True)

    for index, region in enumerate(portable.get("regions", []), start=1):
        if "mask" not in region:
            continue
        source = resolve_mask_path(region["mask"], recipe_dir)
        if not source.is_file():
            raise FileNotFoundError(f"Mask file not found: {source}")
        with Image.open(source) as opened:
            opened.convert("L").save(asset_dir / f"region_{index:03d}.png", format="PNG")
        region["mask"] = f"{asset_dir_name}/region_{index:03d}.png"

    destination = SAVED_RECIPES_DIR / f"{slug}.json"
    destination.write_text(json.dumps(portable, indent=2), encoding="utf-8")
    return destination


with st.sidebar:
    st.header("Recipe")
    saved_files = sorted(SAVED_RECIPES_DIR.glob("*.json"))
    saved_options = ["Built-in example"] + [path.name for path in saved_files]
    selected_preset = st.selectbox("Load a saved preset", saved_options)
    recipe_upload = st.file_uploader("Or upload a JSON recipe", type=["json"])

    if recipe_upload is not None:
        recipe_text = recipe_upload.getvalue().decode("utf-8")
        base_recipe_dir = Path.cwd()
        selected_recipe_key = f"upload-{sha256(recipe_upload.getvalue()).hexdigest()[:12]}"
    elif selected_preset == "Built-in example":
        default_path = Path("recipes/example.json")
        recipe_text = default_path.read_text(encoding="utf-8")
        base_recipe_dir = default_path.resolve().parent
        selected_recipe_key = "built-in-example"
    else:
        selected_path = SAVED_RECIPES_DIR / selected_preset
        recipe_text = selected_path.read_text(encoding="utf-8")
        base_recipe_dir = selected_path.resolve().parent
        selected_recipe_key = f"saved-{selected_path.name}"

    st.download_button(
        "Download loaded JSON",
        recipe_text,
        file_name="photo_recipe.json",
        mime="application/json",
    )

photo = st.file_uploader(
    "Choose a photo",
    type=["jpg", "jpeg", "png", "webp", "tif", "tiff", "bmp", "heic", "heif"],
)
recipe_text = st.text_area(
    "Base recipe (JSON)",
    value=recipe_text,
    height=300,
    key=f"recipe-editor-{selected_recipe_key}",
)
mask_uploads = st.file_uploader(
    "Optional mask files referenced by the base recipe",
    type=["png", "jpg", "jpeg", "bmp", "tif", "tiff"],
    accept_multiple_files=True,
    help="White pixels apply the local adjustment; black pixels protect the image.",
)

if photo is None:
    st.info("Upload a photo to start. HEIC and HEIF are supported.")
    st.markdown(
        "### V0.2 workflow\n"
        "1. Upload a photo and a base JSON recipe.\n"
        "2. Paint separate masks for sky, subject, water, or any area you choose.\n"
        "3. Set independent adjustments and feathering for each layer.\n"
        "4. Preview the result and download the image or a portable recipe bundle."
    )
else:
    try:
        image_bytes = photo.getvalue()
        image_id = sha256(image_bytes).hexdigest()[:16]
        loaded_image = load_image(BytesIO(image_bytes), filename=photo.name)
        source_format = (
            loaded_image.info.get("_source_format")
            or Path(photo.name).suffix.lstrip(".")
            or "JPEG"
        ).upper()
        source_image = loaded_image.convert("RGB")

        recipe = json.loads(recipe_text)
        validate_recipe(recipe)

        uploaded_masks: dict[str, str] = {}
        for mask_file in mask_uploads:
            original_name = Path(mask_file.name).name
            safe_stem = slugify(Path(original_name).stem)
            suffix = Path(original_name).suffix.lower() or ".png"
            payload = mask_file.getvalue()
            payload_hash = sha256(payload).hexdigest()[:8]
            saved_path = MASKS_DIR / f"upload_{image_id}_{safe_stem}_{payload_hash}{suffix}"
            saved_path.write_bytes(payload)
            uploaded_masks[original_name.lower()] = str(saved_path.resolve())

        for region in recipe.get("regions", []):
            if "mask" in region:
                requested_name = Path(region["mask"]).name.lower()
                if requested_name in uploaded_masks:
                    region["mask"] = uploaded_masks[requested_name]

        session_key = f"photograding_layers_{image_id}"
        if session_key not in st.session_state:
            st.session_state[session_key] = {}
        image_layers: dict = st.session_state[session_key]

        st.divider()
        st.header("Local adjustment layers")
        st.caption(
            "Paint white to include an area; switch to Erase and paint black to remove it. "
            "Create one layer for the sky, another for the person, another for the water, etc."
        )

        scale = min(1.0, 500 / source_image.width, 680 / source_image.height)
        canvas_width = max(1, int(round(source_image.width * scale)))
        canvas_height = max(1, int(round(source_image.height * scale)))
        display_image = source_image.resize(
            (canvas_width, canvas_height), Image.Resampling.LANCZOS
        )

        with st.expander("Create or edit a painted mask", expanded=True):
            layer_name = st.text_input(
                "Layer name",
                value="Sky",
                key=f"layer-name-{image_id}",
                help="Use descriptive names such as Sky, Subject, Water, or Background.",
            )
            layer_slug = slugify(layer_name)
            tool_mode = st.selectbox(
                "Brush mode",
                ["Paint (add to mask)", "Erase (remove from mask)"],
                key=f"brush-mode-{image_id}",
            )
            brush_size = st.slider(
                "Brush size", min_value=2, max_value=100, value=28,
                key=f"brush-size-{image_id}",
            )
            stroke_color = "#FFFFFF" if tool_mode.startswith("Paint") else "#000000"

            photo_col, mask_col = st.columns(2)
            with photo_col:
                st.markdown("**Photo reference**")
                st.image(display_image, caption="Use this image to guide your brush strokes.")
            with mask_col:
                st.markdown("**Paint mask**")
                canvas_result = st_canvas(
                    fill_color="rgba(255, 255, 255, 0.0)",
                    stroke_width=brush_size,
                    stroke_color=stroke_color,
                    background_color="#000000",
                    update_streamlit=True,
                    height=canvas_height,
                    width=canvas_width,
                    drawing_mode="freedraw",
                    return_image_data=True,
                    key=f"mask-canvas-{image_id}-{layer_slug}",
                )

            st.caption(
                "The canvas is a black-and-white mask. Use the canvas toolbar to undo, redo, "
                "or clear strokes. You can resize the brush and switch to Erase at any time."
            )

            st.markdown("**Adjustments for this mask**")
            c1, c2, c3 = st.columns(3)
            with c1:
                local_exposure = st.slider(
                    "Exposure (EV)", -5.0, 5.0, 0.0, 0.05,
                    key=f"layer-exposure-{image_id}-{layer_slug}",
                )
                local_contrast = st.slider(
                    "Contrast", 0.0, 3.0, 1.0, 0.05,
                    key=f"layer-contrast-{image_id}-{layer_slug}",
                )
                local_highlights = st.slider(
                    "Highlights", -100, 100, 0,
                    key=f"layer-highlights-{image_id}-{layer_slug}",
                    help="Positive values reduce bright-region intensity; negative values lift it.",
                )
            with c2:
                local_shadows = st.slider(
                    "Shadows", -100, 100, 0,
                    key=f"layer-shadows-{image_id}-{layer_slug}",
                )
                local_temperature = st.slider(
                    "Temperature", -100, 100, 0,
                    key=f"layer-temperature-{image_id}-{layer_slug}",
                )
                local_tint = st.slider(
                    "Tint", -100, 100, 0,
                    key=f"layer-tint-{image_id}-{layer_slug}",
                )
            with c3:
                local_saturation = st.slider(
                    "Saturation", -100, 100, 0,
                    key=f"layer-saturation-{image_id}-{layer_slug}",
                )
                local_vibrance = st.slider(
                    "Vibrance", -100, 100, 0,
                    key=f"layer-vibrance-{image_id}-{layer_slug}",
                )
                local_sharpen = st.slider(
                    "Sharpen", 0.0, 2.0, 0.0, 0.05,
                    key=f"layer-sharpen-{image_id}-{layer_slug}",
                )
            feather = st.slider(
                "Mask feather (pixels)", min_value=0, max_value=200, value=24,
                key=f"layer-feather-{image_id}-{layer_slug}",
                help="Softens the mask edge to reduce visible transitions.",
            )
            current_adjustments = {
                "exposure_ev": local_exposure,
                "contrast": local_contrast,
                "highlights": local_highlights,
                "shadows": local_shadows,
                "temperature": local_temperature,
                "tint": local_tint,
                "saturation": local_saturation,
                "vibrance": local_vibrance,
                "sharpen": local_sharpen,
            }
            # Once a layer exists, its sliders update the live preview immediately.
            if layer_slug in image_layers:
                image_layers[layer_slug]["adjustments"] = current_adjustments
                image_layers[layer_slug]["feather"] = feather

            if st.button("Save / update this layer", type="primary", key=f"save-layer-{image_id}-{layer_slug}"):
                if canvas_result.image_data is None:
                    st.warning("Paint at least part of the mask before saving this layer.")
                else:
                    mask = canvas_image_to_mask(
                        canvas_result.image_data,
                        output_size=(source_image.width, source_image.height),
                    )
                    if not np.any(mask):
                        st.warning("The mask is empty. Paint a white area before saving.")
                    else:
                        mask_path = MASKS_DIR / f"{image_id}_{layer_slug}.png"
                        Image.fromarray(mask, mode="L").save(mask_path)
                        image_layers[layer_slug] = {
                            "name": layer_name.strip() or layer_slug,
                            "mask_path": str(mask_path.resolve()),
                            "feather": feather,
                            "adjustments": current_adjustments,
                        }
                        st.success(f"Saved layer: {layer_name.strip() or layer_slug}")

        if image_layers:
            st.markdown("**Saved layers for this photo**")
            for saved_slug, saved_layer in list(image_layers.items()):
                info_col, action_col = st.columns([5, 1])
                with info_col:
                    st.write(
                        f"**{saved_layer['name']}** — "
                        f"{saved_layer['adjustments'].get('exposure_ev', 0):+.2f} EV, "
                        f"{saved_layer.get('feather', 0)} px feather"
                    )
                with action_col:
                    if st.button("Remove", key=f"remove-layer-{image_id}-{saved_slug}"):
                        Path(saved_layer["mask_path"]).unlink(missing_ok=True)
                        del image_layers[saved_slug]
                        st.rerun()

        runtime_recipe = deepcopy(recipe)
        runtime_recipe.setdefault("regions", [])
        for saved_layer in image_layers.values():
            runtime_recipe["regions"].append(
                {
                    "name": saved_layer["name"],
                    "mask": saved_layer["mask_path"],
                    "feather": saved_layer["feather"],
                    "adjustments": saved_layer["adjustments"],
                }
            )
        validate_recipe(runtime_recipe)
        runtime_recipe["_recipe_dir"] = str(base_recipe_dir)

        name_col, save_col = st.columns([2, 1])
        with name_col:
            preset_name = st.text_input(
                "Preset name to save on this server",
                value="my_photo_recipe",
                key=f"preset-name-{image_id}",
            )
        with save_col:
            st.write("")
            st.write("")
            save_preset_clicked = st.button("Save preset to server", key=f"save-preset-{image_id}")
        if save_preset_clicked:
            try:
                preset_path = save_preset(runtime_recipe, base_recipe_dir, preset_name)
                st.success(f"Saved preset: {preset_path.name}. It will appear in the sidebar on refresh.")
            except (OSError, ValueError) as exc:
                st.error(f"Could not save preset: {exc}")

        source_array = np.asarray(source_image, dtype=np.uint8)
        started = time.perf_counter()
        edited = process_array(source_array, runtime_recipe)
        elapsed = time.perf_counter() - started

        st.divider()
        st.subheader("Before / after")
        st.caption(
            f"Processed {source_image.width:,} × {source_image.height:,} "
            f"({source_image.width * source_image.height / 1_000_000:.1f} MP) "
            f"in {elapsed:.3f} seconds using {len(runtime_recipe.get('regions', []))} local layer(s)."
        )
        original_col, edited_col = st.columns(2)
        with original_col:
            st.markdown("**Original**")
            st.image(source_image, use_container_width=True)
        with edited_col:
            st.markdown("**Edited**")
            st.image(edited, use_container_width=True)

        output_cfg = runtime_recipe.get("output", {})
        selected_format = output_cfg.get("format", "preserve").lower()
        if selected_format == "preserve":
            selected_format = {
                "JPG": "jpeg", "JPEG": "jpeg", "PNG": "png", "WEBP": "webp"
            }.get(source_format, "jpeg")
        if selected_format == "jpg":
            selected_format = "jpeg"
        image_format = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}[selected_format]
        mime = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[selected_format]
        extension = {"jpeg": "jpg", "png": "png", "webp": "webp"}[selected_format]

        output_image = Image.fromarray(edited, mode="RGB")
        max_width, max_height = output_cfg.get("max_width"), output_cfg.get("max_height")
        if max_width or max_height:
            output_image.thumbnail(
                (max_width or output_image.width, max_height or output_image.height),
                Image.Resampling.LANCZOS,
            )
        output_buffer = BytesIO()
        save_kwargs = (
            {"quality": output_cfg.get("quality", 95)}
            if selected_format in {"jpeg", "webp"}
            else {}
        )
        output_image.save(output_buffer, format=image_format, **save_kwargs)
        output_name = (
            f"{Path(photo.name).stem}"
            f"{output_cfg.get('suffix', '_graded')}.{extension}"
        )
        st.download_button(
            "Download edited photo",
            output_buffer.getvalue(),
            file_name=output_name,
            mime=mime,
            type="primary",
        )

        bundle_bytes = package_recipe(runtime_recipe, base_recipe_dir)
        st.download_button(
            "Download recipe + masks (ZIP)",
            bundle_bytes,
            file_name=f"{Path(photo.name).stem}_photograding_recipe.zip",
            mime="application/zip",
        )

    except (json.JSONDecodeError, RecipeError, ValueError, OSError, RuntimeError, KeyError) as exc:
        st.error(f"Could not process image: {exc}")
