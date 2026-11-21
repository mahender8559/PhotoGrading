from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps
import numpy as np

from photograding.recipe import validate_recipe, RecipeError
from photograding.processor import process_array

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

photo = st.file_uploader("Choose a photo", type=["jpg", "jpeg", "png", "webp", "tif", "tiff", "bmp"])
recipe_text = st.text_area("Editing parameters (JSON)", recipe_text, height=440)

if photo:
    try:
        recipe = json.loads(recipe_text)
        validate_recipe({k: v for k, v in recipe.items() if not k.startswith("_")})
        raw = Image.open(photo)
        image = ImageOps.exif_transpose(raw).convert("RGB")
        arr = np.asarray(image)
        edited = process_array(arr, recipe)
        left, right = st.columns(2)
        with left:
            st.subheader("Original")
            st.image(image, use_container_width=True)
        with right:
            st.subheader("Edited")
            st.image(edited, use_container_width=True)
        output = Image.fromarray(edited, "RGB")
        buf = tempfile.SpooledTemporaryFile()
        output.save(buf, format="JPEG", quality=95)
        buf.seek(0)
        st.download_button("Download edited image", buf.getvalue(), file_name=f"{Path(photo.name).stem}_graded.jpg", mime="image/jpeg", type="primary")
    except (json.JSONDecodeError, RecipeError, ValueError, OSError, FileNotFoundError) as exc:
        st.error(f"Could not process image: {exc}")
else:
    st.info("Upload a photo to preview the recipe. The original image is never modified.")
