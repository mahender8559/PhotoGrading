import numpy as np
import pytest

from photograding.processor import process_array
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


def test_unknown_parameter_rejected():
    with pytest.raises(RecipeError):
        validate_recipe({"version": 1, "global": {"exposre_ev": 1}})
