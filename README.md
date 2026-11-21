# PhotoGrading

A deterministic, parameter-driven photo processing tool. Supply an image and a JSON recipe; the processor applies specified pixel operations without AI analysis or generative image editing.

## V0.2

- Global exposure, contrast, highlights, shadows, white balance, saturation and vibrance.
- RGB channel gains and tone curves.
- HSL adjustments by colour range and three-way colour grading.
- Local adjustments using rectangles, polygons or grayscale masks.
- Manual brush masks with paint/erase modes, undo/redo and feathering.
- Independent local adjustment controls for each named mask layer.
- HEIC/HEIF input via pillow-heif, including EXIF orientation.
- Before/after preview, output download, saved server presets, and portable recipe-plus-mask ZIP export.
- Original input files are never overwritten.

Masks are user-created. The application does not automatically detect skies, people or faces.

## Run with Docker on Ubuntu Home Server

Requirements: Docker Engine and the Docker Compose plugin.

    git clone https://github.com/mahender8559/PhotoGrading.git
    cd PhotoGrading
    docker compose up -d --build

Open http://HOME-SERVER-IP:8501 in your browser. For Tailscale, use http://TAILSCALE-IP:8501.

To use another host port, create a .env file next to compose.yaml containing PHOTOGRADING_PORT=8502, then run docker compose up -d.

### Persistent data and updates

Saved presets and mask files live in the Docker named volume photograding_data, not inside the disposable container. They remain available after container recreation and image upgrades.

Update with git pull followed by docker compose up -d --build. Check health with docker compose ps and logs with docker compose logs -f photograding.

Stop with docker compose down. This does not delete the persistent volume. To deliberately remove all saved presets and masks as well, run docker compose down -v. This permanently deletes PhotoGrading's persistent Docker volume.

### Network safety

Streamlit does not provide user authentication in this configuration. Keep the port on your trusted LAN/Tailscale network; do not forward it directly from the public internet. Do not expose it through a public reverse proxy without adding authentication.

## Windows development

Recommended: Python 3.14 (3.11 is also covered by CI).

    py -3.14 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    python -m streamlit run app.py

Or double-click run_windows.bat to create the virtual environment, install dependencies and launch the app.

## CLI

    python -m photograding.cli process --input photo.jpg --recipe recipes/example.json --output-dir output

## Recipe format

See recipes/example.json, recipes/local_masks_example.json, and docs/RECIPE_FORMAT.md.

- Mask pixels are grayscale: white means full effect, black means no effect, grey means proportional effect.
- Coordinates use pixel values after EXIF orientation is applied.
- HEIC/HEIF input is exported as JPEG when output format is set to preserve.
- RAW camera files and full 10-bit/HDR processing are not supported yet.

The initial image pipeline operates in 8-bit sRGB. Operations are deterministic, and mask selection is explicit and under the user's control.
