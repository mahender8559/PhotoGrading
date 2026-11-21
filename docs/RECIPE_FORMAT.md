# PhotoGrading recipe format (v1)

A recipe is a UTF-8 JSON object. Unknown keys are rejected so misspelled instructions do not silently go unnoticed.

## Coordinate conventions

- Coordinates are measured in pixels in the decoded image after EXIF orientation is applied.
- Rectangle: [x, y, width, height].
- Polygon: list of [x, y] vertices.
- Mask image: path relative to the recipe file or an absolute path. White (255) applies the full local adjustment; black (0) applies none; grey applies proportionally.
- Feather is a Gaussian blur radius in pixels.

## Global parameters

- exposure_ev: -5 to +5; exposure compensation in stops.
- contrast: 0 to 3; 1 is neutral.
- brightness: -1 to +1; additive offset in normalized display values.
- highlights: -100 to +100; positive reduces bright-region intensity, negative lifts it.
- shadows: -100 to +100; positive lifts dark-region intensity, negative deepens it.
- temperature and tint: -100 to +100.
- saturation and vibrance: -100 to +100.
- red_gain, green_gain, blue_gain: 0 to 3; 1 is neutral.
- gamma: 0.1 to 4; 1 is neutral.
- vignette and grain: 0 to 1.
- sharpen: 0 to 2.

## Curves, HSL and colour grading

Curves are arrays of [input, output] points for master, red, green and blue; values are 0..255 and input values must increase strictly.

HSL is an object keyed by red, orange, yellow, green, aqua, blue, purple or magenta. Each colour accepts hue (-180..180), saturation (-100..100) and luminance (-100..100).

Three-way colour grading supports shadows, midtones and highlights. Each zone accepts hue (0..360), saturation (0..100), and luminance (-100..100). Balance (-100..100) shifts the tonal weighting boundaries.

## Local regions

Each region contains exactly one selector: rectangle [x, y, width, height], polygon [[x,y], ...], or mask image path.

A region may also contain name, feather (0..200 pixels) and adjustments. Local adjustments support exposure_ev, contrast, brightness, highlights, shadows, temperature, tint, saturation, vibrance, RGB gains, gamma and sharpen. HSL, curves, three-way colour grading and vignette/grain remain global-only.

The V0.2 Streamlit interface can paint and erase grayscale mask layers manually. Save a preset on the server, or download a recipe ZIP containing the recipe and all referenced mask PNGs.

## Output

- format: preserve, JPEG, PNG or WEBP.
- quality: 1..100 (JPEG/WEBP).
- suffix: output filename suffix.
- max_width, max_height: optional maximum dimensions; aspect ratio is preserved.

## Supported input formats

JPEG, PNG, WebP, TIFF, BMP and HEIC/HEIF are supported. HEIC/HEIF decoding uses pillow-heif. EXIF orientation is applied after decoding. When output.format is preserve, HEIC/HEIF inputs are exported as JPEG.

## Processing order

1. Decode image and apply EXIF orientation.
2. Apply global adjustments.
3. Apply master/RGB curves.
4. Apply HSL colour-range adjustments.
5. Apply three-way colour grading.
6. Apply global vignette and grain.
7. Apply local regions in the order listed in the recipe; each region blends its adjusted result through its mask.
8. Resize (if configured) and encode the output.
