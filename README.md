# PhotoGrading

A deterministic, parameter-driven photo processing tool. Supply an image and a JSON recipe; the processor applies the specified pixel operations without AI analysis or generative image editing.

## Current scope

- Global exposure (EV), contrast, highlights, shadows, temperature, tint, saturation and vibrance.
- RGB channel gains and tone curves.
- HSL adjustments by colour range.
- Three-way colour grading: shadows, midtones and highlights with hue, saturation, luminance and balance.
- Local adjustments using rectangles, polygons or grayscale mask images.
- Optional feathering/blur on geometric masks.
- Vignette, grain, sharpening and resize/output settings.
- Streamlit test interface with before/after preview.
- Original files are never overwritten.

## Windows quick start

Requires Python 3.11+.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

Or double-click `run_windows.bat` to create the virtual environment, install dependencies and launch the app.

Open the local URL printed by Streamlit (normally http://localhost:8501). The app displays processing time and input resolution so you can compare performance across your photos.

## CLI

```powershell
python -m photograding.cli process --input photo.jpg --recipe recipes/example.json --output-dir output
```

## Recipe format

See `recipes/example.json` for a global grade, `recipes/local_masks_example.json` for rectangle/mask-based local edits, and `docs/RECIPE_FORMAT.md` for the full specification. Coordinates use pixel coordinates in the original image: rectangle [x, y, width, height], polygon [[x,y], ...]. For a mask file, white means full effect and black means no effect.

Parameter definitions are explicit in the recipe documentation. Operations are deterministic and applied in a documented order. The implementation uses Pillow and NumPy for predictable pixel operations; OpenCV is used for spatial masks/blur where appropriate.

## Notes

- V1 loads ordinary raster formats supported by Pillow. RAW camera files are not yet supported.
- Processing is performed in 8-bit sRGB for this initial test build. A later version can add higher-bit-depth/linear-light workflows.
- Face targeting is intentionally not automatic. Supply a mask image or coordinates when you want a local adjustment.
