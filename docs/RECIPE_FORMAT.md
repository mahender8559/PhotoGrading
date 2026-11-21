# PhotoGrading recipe format (v1)

A recipe is a UTF-8 JSON object. Unknown keys are rejected so misspelled instructions do not silently go unnoticed.

## Coordinate conventions

- Coordinates are measured in pixels in the decoded image after EXIF orientation is applied.
- Rectangle: [x, y, width, height].
- Polygon: list of [x, y] vertices.
- Mask image: path relative to the recipe file or an absolute path. White (255) applies the full local adjustment; black (0) applies none; grey applies proportionally.
- Feather is a Gaussian blur radius in pixels. It softens geometric masks; external grayscale masks can also be feathered.

## Parameters

### global
- exposure_ev: -5 to +5; exposure compensation in stops.
- contrast: 0 to 3; 1 is neutral.
- brightness: -1 to +1; additive offset in normalized display values.
- highlights: -100 to +100; positive reduces bright-region intensity, negative lifts it.
- shadows: -100 to +100; positive lifts dark-region intensity, negative deepens it.
- temperature: -100 to +100; positive warms, negative cools.
- tint: -100 to +100; positive magenta, negative green.
- saturation: -100 to +100.
- vibrance: -100 to +100.
- red_gain, green_gain, blue_gain: 0 to 3; 1 is neutral.
- gamma: 0.1 to 4; 1 is neutral.
- vignette: 0 to 1.
- grain: 0 to 1.
- sharpen: 0 to 2.

### curves
Optional arrays of [input, output] points for red, green, blue and master. Values are 0..255. Each channel needs at least two points with strictly increasing input values.

### hsl
Optional object keyed by red, orange, yellow, green, aqua, blue, purple, magenta. Each colour accepts hue (-180..180 degrees), saturation (-100..100), and luminance (-100..100).

### regions
Each region contains exactly one selector:
- rectangle: [x, y, width, height]
- polygon: [[x,y], ...]
- mask: image path

Each region has optional feather (0..200 pixels) and adjustments. Local adjustments support exposure_ev, contrast, brightness, highlights, shadows, temperature, tint, saturation, vibrance, RGB gains, gamma and sharpen. HSL/curves/effects are global-only in v1.

### output
- format: preserve, JPEG, PNG or WEBP.
- quality: 1..100 (JPEG/WEBP).
- suffix: output filename suffix.
- max_width, max_height: optional maximum dimensions; aspect ratio is preserved.

See recipes/example.json for a complete example.
