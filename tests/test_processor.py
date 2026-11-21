import numpy as np
import pytest
from PIL import Image

from photograding.processor import process_array, process_file
from photograding.recipe import validate_recipe, RecipeError


def test_neutral_recipe_is_identity():
    arr = np.full((20, 30, 3), 128, dtype=np.uint8)
    result = process_array(arr, {"version": 1, "global": {}})
    assert np.array_equal(result, arr)


def test_exposure_brightens():
    arr = np.full((10, 10, 3), 80, dtype=np.uint8)
    result = process_array(arr, {"version": 1, "global": {"exposure_ev": 1}})
    assert result.mean() > arr.mean()


def test_rectangle_local_adjustment():
    arr = np.full((30, 30, 3), 80, dtype=np.uint8)
    recipe = {"version": 1, "global": {}, "regions": [
        {"rectangle": [5, 5, 10, 10], "adjustments": {"exposure_ev": 1}}
    ]}
    result = process_array(arr, recipe)
    assert result[10, 10, 0] > arr[10, 10, 0]
    assert result[0, 0, 0] == arr[0, 0, 0]


def test_polygon_mask_adjustment():
    arr = np.full((30, 30, 3), 80, dtype=np.uint8)
    recipe = {"version": 1, "global": {}, "regions": [
        {"polygon": [[5, 5], [20, 5], [20, 20], [5, 20]], "adjustments": {"exposure_ev": 1}}
    ]}
    result = process_array(arr, recipe)
    assert result[10, 10, 0] > arr[10, 10, 0]
    assert result[0, 0, 0] == arr[0, 0, 0]


def test_three_way_color_grading_changes_selected_tone():
    arr = np.full((20, 20, 3), [75, 75, 75], dtype=np.uint8)
    recipe = {"version": 1, "global": {}, "color_grading": {
        "shadows": {"hue": 210, "saturation": 40}
    }}
    result = process_array(arr, recipe)
    assert not np.array_equal(result, arr)


def test_unknown_parameter_rejected():
    with pytest.raises(RecipeError):
        validate_recipe({"version": 1, "global": {"exposre_ev": 1}})


def test_invalid_output_format_rejected():
    with pytest.raises(RecipeError):
        validate_recipe({"version": 1, "output": {"format": 42}})


def test_png_output_preserves_original_file(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (12, 8), (80, 90, 100)).save(source)
    recipe = {"version": 1, "global": {"exposure_ev": 0.2},
              "output": {"format": "preserve", "suffix": "_graded"}}
    result = process_file(source, recipe, tmp_path / "output")
    assert result.suffix == ".png"
    assert source.exists()
    assert Image.open(source).size == Image.open(result).size


def test_sample_recipe_is_valid():
    from photograding.recipe import load_recipe
    from pathlib import Path

    recipe = load_recipe(Path("recipes") / "example.json")
    assert recipe["version"] == 1



def test_grayscale_mask_adjustment(tmp_path):
    from PIL import Image

    arr = np.full((20, 20, 3), 80, dtype=np.uint8)
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[5:15, 5:15] = 255
    Image.fromarray(mask, "L").save(tmp_path / "mask.png")
    recipe = {"version": 1, "global": {}, "regions": [
        {"mask": "mask.png", "adjustments": {"exposure_ev": 1}}
    ]}
    result = process_array(arr, recipe, recipe_dir=tmp_path)
    assert result[10, 10, 0] > arr[10, 10, 0]
    assert result[0, 0, 0] == arr[0, 0, 0]


def test_local_mask_example_recipe_is_valid():
    from photograding.recipe import load_recipe
    from pathlib import Path

    recipe = load_recipe(Path("recipes") / "local_masks_example.json")
    assert len(recipe["regions"]) == 2


def test_output_never_overwrites_original(tmp_path):
    source = tmp_path / "photo.png"
    Image.new("RGB", (8, 8), (50, 60, 70)).save(source)
    recipe = {"version": 1, "global": {}, "output": {"format": "preserve", "suffix": ""}}
    with pytest.raises(ValueError, match="overwrite the original"):
        process_file(source, recipe, tmp_path)


def test_heic_input_is_decoded_and_preserve_exports_jpeg(tmp_path):
    pytest.importorskip("pillow_heif")

    source = tmp_path / "phone_photo.heic"
    Image.new("RGB", (16, 10), (80, 100, 120)).save(source, format="HEIF", quality=95)

    # Exercise the same in-memory upload path used by the Streamlit interface.
    from io import BytesIO
    from photograding.processor import load_image

    loaded = load_image(BytesIO(source.read_bytes()), filename=source.name)
    assert loaded.size == (16, 10)
    assert loaded.info["_source_format"] in {"HEIF", "HEIC"}

    recipe = {"version": 1, "global": {}, "output": {"format": "preserve"}}
    result = process_file(source, recipe, tmp_path / "output")
    assert result.suffix == ".jpeg"
    with Image.open(result) as exported:
        assert exported.format == "JPEG"
        assert exported.size == (16, 10)


def test_load_image_applies_exif_orientation(tmp_path):
    from photograding.processor import load_image

    source = tmp_path / "oriented.jpg"
    image = Image.new("RGB", (12, 8), (120, 80, 40))
    exif = Image.Exif()
    exif[274] = 6
    image.save(source, format="JPEG", exif=exif.tobytes())

    loaded = load_image(source)
    assert loaded.size == (8, 12)
