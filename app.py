from __future__ import annotations

import json
from pathlib import Path
from io import BytesIO
import tempfile
import time

import streamlit as st
from PIL import Image
import numpy as np

from photograding.recipe import validate_recipe, RecipeError
from photograding.processor import process_array, load_image

st.set_page_config(page_title="PhotoGrading", page_icon="🎨", layout="wide")
st.title("PhotoGrading")
st.caption("Deterministic image editing from explicit JSON parameters — no AI analysis or generative editing.")

with st.sidebar:
    st.header("Recipe")
    recipe_upload = st.file_uploader("Upload JSON recipe", type=["json"])
    default_recipe_path = Path("recipes/example.json")
    if recipe_upload:
        recipe_text = recipe_upload.getvalue().decode("utf-8")
    else:
        recipe_text = default_recipe_path.read_text(encoding="utf-8")
    st.download_button("Download current recipe", recipe_text, file_name="photo_recipe.json", mime="application/json")

photo = st.file_uploader("Choose a photo", type=["jpg", "jpeg", "png", "webp", "tif", "tiff", "bmp", "heic", "heif"])
recipe_text = st.text_area("Editing parameters (JSON)", recipe_text, height=440)
mask_uploads = st.file_uploader(
    "Optional mask images referenced by the recipe",
    type=["png", "jpg", "jpeg", "bmp", "tif", "tiff"],
    accept_multiple_files=True,
    help="For each region with a \"mask\" path, upload a file with the same filename. White applies the edit; black protects the pixel."
)

if photo:
    try:
        recipe = json.loads(recipe_text)
        validate_recipe({k: v for k, v in recipe.items() if not k.startswith("_")})
        image = load_image(BytesIO(photo.getvalue()), filename=photo.name)
        source_format = (image.info.get("_source_format") or Path(photo.name).suffix.lstrip(".") or "JPEG").upper()
        image = image.convert("RGB")
        # Uploaded masks are copied into a temporary workspace for this run.
        with tempfile.TemporaryDirectory(prefix="photograding_masks_") as mask_dir:
            uploaded_by_name = {}
            for mask_file in mask_uploads:
                safe_name = Path(mask_file.name).name
                target = Path(mask_dir) / safe_name
                target.write_bytes(mask_file.getvalue())
                uploaded_by_name[safe_name.lower()] = str(target)
            for region in recipe.get("regions", []):
                if "mask" in region:
                    requested_name = Path(region["mask"]).name.lower()
                    if requested_name in uploaded_by_name:
                        region["mask"] = uploaded_by_name[requested_name]
            recipe["_recipe_dir"] = mask_dir
            arr = np.asarray(image)
            started = time.perf_counter()
            edited = process_array(arr, recipe)
            elapsed = time.perf_counter() - started
        st.caption(f"Processed {image.width:,} × {image.height:,} ({image.width * image.height / 1_000_000:.1f} MP) in {elapsed:.3f} seconds.")
        left, right = st.columns(2)
        with left:
            st.subheader("Original")
            st.image(image, use_container_width=True)
        with right:
            st.subheader("Edited")
            st.image(edited, use_container_width=True)
        output = Image.fromarray(edited, "RGB")
        output_cfg = recipe.get("output", {})
        selected_format = output_cfg.get("format", "preserve").lower()
        if selected_format == "preserve":
            selected_format = {"JPG": "jpeg", "JPEG": "jpeg", "PNG": "png", "WEBP": "webp"}.get(source_format, "jpeg")
        if selected_format == "jpg":
            selected_format = "jpeg"
        image_format = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}[selected_format]
        mime = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[selected_format]
        extension = {"jpeg": "jpg", "png": "png", "webp": "webp"}[selected_format]
        max_w, max_h = output_cfg.get("max_width"), output_cfg.get("max_height")
        if max_w or max_h:
            output.thumbnail((max_w or output.width, max_h or output.height), Image.Resampling.LANCZOS)
        buf = BytesIO()
        save_kwargs = {"quality": output_cfg.get("quality", 95)} if selected_format in {"jpeg", "webp"} else {}
        output.save(buf, format=image_format, **save_kwargs)
        st.download_button("Download edited image", buf.getvalue(), file_name=f"{Path(photo.name).stem}{output_cfg.get('suffix', '_graded')}.{extension}", mime=mime, type="primary")
    except (json.JSONDecodeError, RecipeError, ValueError, OSError, FileNotFoundError, RuntimeError) as exc:
        st.error(f"Could not process image: {exc}")
else:
    st.info("Upload a photo to preview the recipe. The original image is never modified.")
