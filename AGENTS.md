# Synesthesia Project Conventions

## Project overview

Four interactive tools for MIDI visualization, composition, and LFI theory
exploration, all using the
**Liminal Flow Intonation (LFI)** color system — not Western 12-tone theory.

### Applications (canonical source in `src/synestesia/`)

- **`src/synestesia/composer/app.py`** — piano-roll node-based composer with MIDI import/playback
- **`src/synestesia/composer_live/app.py`** — composer + real-time MIDI input, hand mute/hide, connection toggling
- **`src/synestesia/midi_visualizer/app.py`** — MIDI visualizer (Flow view + Piano Roll Tiles/Nodes)
- **`src/synestesia/theory_explorator/app.py`** — LFI Generative Circle, Circle/Line Visualizer, and Interval Relationship View with tone playback

### Project structure

```
synestesia/
├── menu.py                        # Launcher — run with: python menu.py
├── src/
│   └── synestesia/
│       ├── __init__.py
│       ├── __main__.py            # python -m synestesia entry-point
│       ├── engine/                # LFI model layer (shared by all apps)
│       │   ├── core.py            # Color system, audio, MIDI import, drawing helpers
│       │   └── __init__.py
│       ├── composer/
│       │   ├── app.py
│       │   └── __init__.py        # exposes run()
│       ├── composer_live/
│       │   ├── app.py
│       │   └── __init__.py        # exposes run()
│       ├── midi_visualizer/
│       │   ├── app.py
│       │   └── __init__.py        # exposes run()
│       └── theory_explorator/
│           ├── app.py
│           └── __init__.py        # exposes run()
├── tests/
│   └── test_lfi.py                # Pure-math tests (no display required)
├── README.md
├── requirements.txt
├── pyproject.toml
└── AGENTS.md
```



### Running

```bash
python menu.py              # interactive launcher
python -m pytest tests/ -v  # run tests (no display needed)
```

## Naming and terminology

### LFI note-class labels (G0–G11)

The system has 12 note classes named G0 through G11. These are **not** Western
note names (C, D, E, …). They are labels for positions in a self-contained
generative sequence.

`LFI_DATA` is a list of 12 tuples `(chromatic_semitone, name, base_freq, v_value)`
**ordered by ascending frequency** (the LINEAR sequence)

| Index | Entry | v_value | hue    | Description |
|-------|-------|--------:|-------:|-------------|
| 0     | (0, "G0", ...)  | 0.000000 | 240° Blue | frequency anchor |
| 1     | (7, "G7", ...)  | 0.094738 | 274° Violet | next in frequency |
| 2     | (2, "G2", ...)  | 0.169925 | 301° Magenta | |
| 3     | (9, "G9", ...)  | 0.264663 | 335° Rose | |
| 4     | (4, "G4", ...)  | 0.339850 | 2° Red | |
| 5     | (11, "G11", ...)| 0.434588 | 36° Orange | |
| 6     | (6, "G6", ...)  | 0.509775 | 64° Yellow | structural midpoint |
| 7     | (1, "G1", ...)  | 0.584963 | 91° Chartreuse | |
| 8     | (8, "G8", ...)  | 0.679700 | 125° Green | |
| 9     | (3, "G3", ...)  | 0.754888 | 152° Spring | |
| 10    | (10, "G10", ...)| 0.849625 | 186° Cyan | |
| 11    | (5, "G5", ...)  | 0.924813 | 213° Azure | |

**Do NOT index LFI_DATA by chromatic semitone.** Use `SEM` (a dict keyed by
chromatic semitone) for lookup by semitone. Index into `LFI_DATA` only by
LINEAR position (0 = G0, 1 = G7, 2 = G2, …).

The LINEAR sequence (frequency-ascending order):
`G0 → G7 → G2 → G9 → G4 → G11 → G6 → G1 → G8 → G3 → G10 → G5 → G0`

### Chromatic to LFI G-class mapping

The 12 piano-key chromatic positions map to LFI G-classes via
`_LINEAR_CHROMATIC_MAP` in `engine/core.py`:

```python
_LINEAR_CHROMATIC_MAP = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]
```

So the key immediately to the right of G0 (chromatic semitone 1) maps to **G7**
(the LINEAR successor of G0), not G1. All MIDI→LFI color/label functions
(`get_color_relative`, `note_color`, `name`) use this mapping:

```python
g_class = _LINEAR_CHROMATIC_MAP[(midi_note - 60) % 12]
```

### The generative system

The 12 note classes are produced by two generative operators applied to a
starting reference:

- **G+** — multiply frequency by `3/2`
- **G-** — multiply frequency by `4/3`

Starting from any reference, repeated application of G+ and G- (with octave
reduction to keep ratios within [1, 2)) produces the 12 distinct classes.
This is a **frequency-agnostic** mathematical system; it does not depend on any
external tuning standard.

This is the **Generative sequence**. Contrary to the **Linear sequence**, we do not sort this sequence by ascending numerical value, so this is simply the sequence of values produced by applying the generative step repeatedly and normalizing the value inside an octave (modulation mod12). :
`G0 → G1 → G2 → G3 → G4 → G5 → G6 → G7 → G8 → G9 → G10 → G11`

And when this sequence is ordered numerically, it produces the LINEAR SEQUENCE, and is the manifestation of the modulation results:

`G0 → G7 → G2 → G9 → G4 → G11 → G6 → G1 → G8 → G3 → G10 → G5`

After 12 steps the cycle closes (one octave above the starting pitch class).

### G6 — the structural midpoint

In the Linear sequence, **G6 is the 6th step**. Its frequency ratio is the
logarithmic midpoint of the octave — approximately √2 (~1.414). This makes G6
the point of **maximum distance** from G0 within the octave: the structural
opposite of the root.

In Western terminology this interval is called the tritone. That label is
**forbidden** in this project; describe it only as the structural midpoint or
logarithmic opposite of G0, or simply G6.

### Color mapping — sound to light

The color mapping is derived from a logarithmic spiral over frequency: each
octave (×2) is exactly one full rotation (360°) of the hue circle, and the
generative operator G+ (×3/2) is the natural angular step on that spiral.
This makes hue a direct function of log₂(frequency) rather than an ad-hoc RGB
interpolation.

#### Core equation

- Reduce any frequency ratio to the reference octave: r ∈ [1, 2).
- Hue is computed as:

```
hue(r) = (240° + 360° × log₂(r)) mod 360°
```

Notes:
- Anchor 240° = pure bright Blue (G0) simply by convenience. Any color can be used as the anchor, as it represents a frequency in a frequency-agnostic system. 
- When we pick blue as our anchor, we are using the RELATIVE colors (compatible with the western convenience C ≃ 261.63 hz as blue).
- We can also assign any color to this. When we assign blue = 20hz (and octaves), we are using the CANONICAL colors. When we are choosing some different mapping (such as selected by user), we are using CUSTOM colors
- Use HSL(hue, 1.0, 0.5) → convert to sRGB for display (S=1, L=0.5 preserves perceptual purity).
- Compute logs in double precision and avoid quantizing hue unless explicitly required.

Why:
- One octave (log₂ change = 1) → 360° (full rotation).
- A G+ step (×3/2) therefore moves by 360° × log₂(3/2) ≈ 210.587°, the natural
  spiral angle for the perfect fifth. This is the fundamental geometric fact
  and should be used directly; do not force G+ to be 180°.

#### Operators (semantic primitives)

- Oc+ (octave up): Oc+(x) = 2 × x → geometrically +360° (same hue)
- Oc- (octave down): Oc-(x) = x / 2 → geometrically −360° (same hue)
- G+ (generative up / fifth): G+(x) = 3/2 × x → geometrically +360° × log₂(3/2) ≈ +210.587°
- G- (generative down / inverse): G-(x) = 4/3 × x → geometrically −360° × log₂(3/2) (after octave reduction)

Implementation note: apply an operator to the numeric ratio, then reduce to [1,2) before computing hue.

#### Practical rules for agents and code

1. Always derive hue from log₂(ratio) using the formula above. Never approximate hue by interpolating RGB component values across the spectrum.
2. Reduce ratio to [1,2) by repeated octave shifts before computing log₂. The octave count may modulate lightness/brightness in UI, but must not affect hue.
3. Use HSL(h, 1.0, 0.5) as canonical presentation color; convert to sRGB hex for displays and exports.
4. Preserve high precision (double floats) so the small Pythagorean comma remains visible when the UI wants to annotate it.
5. When asked to produce a palette or table, include: ratio (reduced), log₂ fractional part, hue°, and hex color so other systems can reconstruct exactly.

#### Pythagorean facts (as visible artifacts)

- G+ angular step: 360° × log₂(3/2) ≈ 210.587°
- After 12 G+ steps: frequency multiplier = 3¹² / 2¹⁹ ≈ 1.0136432648 (the Pythagorean comma)
- Angular gap after 12 steps = 360° × log₂(3¹² / 2¹⁹) ≈ 7.04°
  - Hue returns almost to the starting angle; the small mismatch is the visible manifestation of the comma.

#### Anchor table (G+^n starting from G0 = ratio 1.0)

(Agents should compute these in real time; the table is included for reference and to make behavior explicit.)

| G+^n  | reduced ratio | log₂ frac | hue (°) | hex (HSL→sRGB, S=1 L=0.5) |
|-------|---------------:|----------:|--------:|---------------------------:|
| G+^0  | 1.000000       | 0.000000  | 240.00° | #0000ff (Blue)             |
| G+^1  | 1.500000       | 0.584963  |  90.59° | #7dff00 (Chartreuse)       |
| G+^2  | 1.125000       | 0.169925  | 301.17° | #ff00fa (Magenta)          |
| G+^3  | 1.687500       | 0.754888  | 151.76° | #00ff87 (Spring Green)     |
| G+^4  | 1.265625       | 0.339850  |   2.35° | #ff0a00 (Red)              |
| G+^5  | 1.898438       | 0.924813  | 212.93° | #0073ff (Azure)            |
| G+^6  | 1.423828       | 0.509775  |  63.52° | #f0ff00 (Yellow)           |
| G+^7  | 1.067871       | 0.094738  | 274.11° | #9100ff (Violet)           |
| G+^8  | 1.601807       | 0.679700  | 124.69° | #00ff14 (Green)            |
| G+^9  | 1.201355       | 0.264663  | 335.28° | #ff0069 (Rose)             |
| G+^10 | 1.802032       | 0.849625  | 185.87° | #00e6ff (Cyan)             |
| G+^11 | 1.351524       | 0.434588  |  36.45° | #ff9b00 (Orange)           |
| G+^12 | 1.013643       | 0.019550  | 247.04° | #1e00ff (near Blue — comma) |

...and so on.



## LFI color-combination layer — positional color disc

This section defines a separate visual/theoretical layer for combining
already-generated LFI colors. It does **not** replace the canonical
sound-to-light mapping. Individual G-class colors must still be derived from the
LFI hue system described above. Once those note colors exist as concrete sRGB
tuples, combinations between them are read from a **positional color disc**.

### Concept

Each G-class is a colored point on the perimeter of the LFI circle, placed at
one of 12 equal 30° angular slots (the regular 12-gon). A selected cluster is a
set of two or more points. The visualizer draws relations between the selected
points and generates new colors from those relations.

The combination color of any set of notes is a **pure function of where their
combined geometric point sits on the wheel**:

- Combining N notes = the geometric center of their rim points (midpoint for 2,
  polygon centroid for 3+). This is the same centroid the visualizer already
  draws.
- The combination **color is read from a color disc at that interior point**.

Because the color depends only on the position of the combined point, **any two
bodies that share a centroid share a color by construction** — this is the
defining property of this layer.

There are two distinct color levels:

1. **1-1 relation color**
   - For every pair of selected G-classes, read the disc color at the exact
     midpoint of the chord between the two rim points.
   - Draw the line between those two points using that pair color.
   - Place a small generated-color circle at the midpoint.

2. **Cluster internal color**
   - For the full selected cluster, read the disc color at the polygon centroid
     of all selected rim points.
   - Use this color as the internal fill color of the selected polygon or shape.
   - Place a generated-color circle at the centroid.

This makes the visualizer show both the pairwise internal relations and the
total compound color of the selected body.

### The color disc

The disc is centered on the wheel center and has the same rim radius `R` as the
12 equal slots.

- **Angle → hue.** Hue varies with the point's angle from the wheel center. At
  any angle, interpolate between the two bracketing rim slots' LFI hues using
  shortest-arc blending (the `_lfi_lerp` idiom). A point exactly on a rim node
  reads that node's exact LFI hue.
  - Hue-by-slot is **not** equally spaced (Pythagorean pattern). Therefore the
    geometric angle must be mapped to hue via the rim nodes' actual LFI hues,
    never via raw angle.
  - Hue source is `ColorState.hue_of(_LINEAR_CHROM[slot])`, read live so both
    standard and custom palettes are supported with no snapshotting.
- **Radius → saturation/lightness.** `t = distance_from_center / R`. Color =
  `HSL(hue, 100%·t, 50%)`. Rim (`t = 1`) = full LFI color; center (`t = 0`) =
  mid-gray (`_hsl` returns gray when `s == 0`).

Reference implementation (`_disc_color` in `theory_explorator/app.py`):

```python
def _disc_color(point, cx, cy, R, cs):
    dx, dy = point[0] - cx, point[1] - cy
    d = math.hypot(dx, dy)
    t = max(0.0, min(1.0, d / R)) if R > 0 else 0.0
    if t < 1e-6:
        return _hsl(0.0, 0.0, 50.0)          # center => gray
    ang = (math.degrees(math.atan2(dy, dx)) + 90.0) % 360.0   # 0 at slot 0
    slot_f = ang / 30.0
    s0 = int(slot_f) % 12
    s1 = (s0 + 1) % 12
    frac = slot_f - int(slot_f)
    h0 = cs.hue_of(_LINEAR_CHROM[s0])
    h1 = cs.hue_of(_LINEAR_CHROM[s1])
    diff = ((h1 - h0 + 180.0) % 360.0) - 180.0   # shortest arc
    hue = (h0 + diff * frac) % 360.0
    return _hsl(hue, 100.0 * t, 50.0)
```

The `+90°` offset and `/30°` slotting encode the same angle convention as
`_circle_point` (`-pi/2 + 2*pi*i/12`, slot 0 at top). The rim invariant is the
key correctness check:

```python
_disc_color(_circle_point(i, cx, cy, R), cx, cy, R, cs) == cs.color(_LINEAR_CHROM[i])
```

(within rounding) for all 12 slots, under both standard and custom palettes.

### Resulting properties

- Point on a node ⇒ that node's exact LFI color (consistency preserved).
- Pair midpoint ⇒ blend of just those two, muted by how far inward the chord
  midpoint sits.
- **Same centroid ⇒ same color** (the goal).
- Center-symmetric bodies (centroid at the wheel center, e.g. step-6 or full
  rings) ⇒ neutral gray.
- Interior points have `t < 1`, so combination colors are generally **less
  saturated** than the rim notes. This muting is intended, not a regression.

### Generated-color objects

The visualizer should internally represent each generated color as a small object so it can be drawn, listed, exported, and tested.

Recommended structure:

```python
GeneratedColor = {
    "kind": "pair" | "cluster",
    "members": [linear_position_0, linear_position_1, ...],
    "labels": ["G0", "G7", ...],
    "rgb": (r, g, b),
    "hex": "#rrggbb",
    "point": (x, y),
}
```

Rules:

- `kind == "pair"` means the generated color belongs to a 1-1 relation.
- `kind == "cluster"` means the generated color belongs to the whole selected body.
- `members` must use LINEAR circle positions, not chromatic keyboard positions.
- `labels` should be displayed in the current LFI labels, never Western note names.
- `point` is where the generated-color circle is drawn.

### Geometry rules

The LFI circle should use 12 equal angular slots. The currently preferred order for the visual cluster tool is the LINEAR sequence:

`G0 → G7 → G2 → G9 → G4 → G11 → G6 → G1 → G8 → G3 → G10 → G5 → G0`

For each selected G-class, compute a perimeter point:

```python
angle = -pi / 2 + 2 * pi * linear_position / 12
x = cx + cos(angle) * radius
y = cy + sin(angle) * radius
```

#### Pair midpoint

For every selected pair `(a, b)`, draw the line from point `a` to point `b`. The generated pair color circle is placed at:

```python
mx = (ax + bx) / 2
my = (ay + by) / 2
```

#### Cluster centroid

For the full selected cluster:

- If one point is selected, the centroid is the point itself.
- If two points are selected, the centroid is the midpoint of the line.
- If three or more points are selected, the centroid should represent the selected polygon/body.

For three or more selected points, the preferred centroid is the polygon centroid when the points form a non-degenerate polygon. Sort selected points by their circle order before computing it.

Polygon centroid formula:

```python
A2 = 0
Cx = 0
Cy = 0
for each edge p[i] -> p[j]:
    cross = x[i] * y[j] - x[j] * y[i]
    A2 += cross
    Cx += (x[i] + x[j]) * cross
    Cy += (y[i] + y[j]) * cross
A = A2 / 2
centroid = (Cx / (6 * A), Cy / (6 * A))
```

If the polygon area is almost zero, fall back to the arithmetic mean of selected point coordinates.

### Listing all selected and generated colors

The visualizer must show a live list containing:

1. **Selected source colors**
   - One row per selected G-class.
   - Show label, RGB, hex, and a small swatch.

2. **Generated pair colors**
   - One row for every possible 1-1 relation inside the selected cluster.
   - For `n` selected notes, there are `n * (n - 1) / 2` pair colors.
   - Show relation label, e.g. `G0 + G7`, RGB, hex, and a small swatch.

3. **Generated cluster color**
   - One row for the full selected cluster.
   - Show all labels, RGB, hex, and a larger or emphasized swatch.

The list must update immediately whenever selection changes.

### Drawing behavior

When the user selects multiple G-classes:

- Selected source nodes should be visually emphasized with a brighter or thicker outline.
- Every selected pair should draw a line between the two nodes.
- Each pair line should be colored by that pair's disc color (read at the chord midpoint).
- Each pair line should have a small generated-color circle exactly at its midpoint.
- If at least three G-classes are selected, draw the polygon/body connecting selected points in circle order.
- The polygon/body fill should use the cluster internal color: the disc color read at the polygon centroid.
- The polygon/body stroke may be the cluster color or a neutral outline, but pairwise relation lines should remain visible.
- Draw a cluster generated-color circle at the polygon centroid.
- The cluster generated-color circle should be visually distinct from pair midpoint circles, for example slightly larger or with a stronger outline.

Recommended sizes:

```python
source_node_radius = 9
selected_node_radius = 13
pair_generated_radius = 5
cluster_generated_radius = 8
line_width = 2
polygon_alpha = 0.25 to 0.35
```

### Interaction requirements

The tool should support:

- Click a node to toggle its selection.
- Clear selection button.
- Fixed-step body buttons: Step 1 through Step 6.
- Optional export/copy list of generated colors.
- Optional hover labels over generated-color circles.

Fixed-step body behavior:

```python
selected.clear()
i = 0
do:
    selected.add(i)
    i = (i + step) % 12
while i != 0
```

This creates recurring bodies from the LINEAR circle positions. Step 6 creates the structural opposite pair. Symmetrical bodies (centroid at or near the wheel center) produce neutral or muted disc colors by construction.

### Pygame implementation notes for `theory_explorator/app.py`

The combination layer lives inside `theory_explorator/app.py` as two modules:

- `RGBClusterMixer` (Module 4)
- `RelationMap` (Module 5)

Both share the single `_disc_color(point, cx, cy, R, cs)` helper, passing their
own `_circle_center_radius()` so a point on slot `i` reads that slot's exact
LFI color in either module.

Suggested helper functions:

```python
def rgb_hex(c):
    return "#%02x%02x%02x" % c

def circle_point(i, cx, cy, r):
    a = -math.pi / 2 + 2 * math.pi * i / 12
    return cx + math.cos(a) * r, cy + math.sin(a) * r

def pair_generated(a, b, points, cx, cy, R, cs):
    ax, ay = points[a]; bx, by = points[b]
    point = ((ax + bx) / 2, (ay + by) / 2)
    color = _disc_color(point, cx, cy, R, cs)
    return {"kind": "pair", "members": [a, b], "rgb": color, "point": point}

def cluster_generated(selected, points, cx, cy, R, cs):
    ordered = sorted(selected)
    point = polygon_or_mean_centroid([points[i] for i in ordered])
    color = _disc_color(point, cx, cy, R, cs)
    return {"kind": "cluster", "members": ordered, "rgb": color, "point": point}
```

Rendering order should be:

1. Base circle and unselected source nodes.
2. Polygon fill using cluster color, if at least three points are selected.
3. Pair relation lines using pair colors.
4. Pair generated-color midpoint circles.
5. Cluster generated-color centroid circle.
6. Selected source nodes and labels on top.
7. Side/bottom list of selected and generated colors.

### Important distinction from canonical LFI color generation

The canonical note colors are still generated from the LFI sound-to-light
system. The positional color disc only applies after those source colors already
exist. Therefore:

- Correct: derive the 12 G-class colors from LFI hue, place them on the rim, then
  read combination colors from the disc at the combined point.
- Incorrect: use the disc or any blending to derive the original 12 G-class
  colors. The source palette is always hue-derived and is NEVER RGB-interpolated.
- Correct: pair and cluster colors are visual relation artifacts.
- Incorrect: pair and cluster colors are new base G-classes.

The earlier equal-part RGB-average combination rule is retired. RGB interpolation
remains forbidden for deriving the LFI palette itself; combination colors are now
defined exclusively by the positional color disc, whose hue still rides the LFI
hue circle (shortest-arc interpolation between bracketing rim slots) rather than
mixing RGB channels.

### Frequency reference ("canonical" values)

The befored mentioned **canonical values reference** is:

- **G0 = 20 Hz** (minimum)
- **Maximum G0 in the system = 20 480 Hz** (10 natural octaves above the base)
These values are very approximate to the minimum and maximum frequencies typically perceived by human auditory senses
These are also power-of-two bounds. The word **"canonical"** is acceptable when it
refers specifically to this base-frequency convention. It is a technical term
of the project, not a forbidden word.

In practice the code uses `F_BASE = 40.0 Hz` and `F_TOP = 10240.0 Hz` for
real-world instrument compatibility; the canonical values remain the theoretical
reference frame, but not the standard presentation in the project due to incompatibility with the world's conventions.

### MIDI compatibility convention

For compatibility with real MIDI instruments, the project accepts the mapping
**C1 = G01** (Western MIDI note 12 maps to G0 in octave 1).

All MIDI→LFI mapping functions use `_LINEAR_CHROMATIC_MAP` to convert the
chromatic keyboard position to an LFI G-class in LINEAR (frequency) order.
This means the 12 chromatic steps per octave map to LFI classes in
frequency-ascending order, NOT in chromatic-label order.

```python
# Reference MIDI note = 60 maps to G0 (blue):
chromatic_semitone = (midi_note - 60) % 12
g_class = _LINEAR_CHROMATIC_MAP[chromatic_semitone]  # LINEAR G-class

# Example: key right of G0 (C#4, MIDI 61):
#   chromatic_semitone = 1 → _LINEAR_CHROMATIC_MAP[1] = 7 → G7 (violet)
# Example: the key 7 chromatic steps above G0 (G4, MIDI 67):
#   chromatic_semitone = 7 → _LINEAR_CHROMATIC_MAP[7] = 1 → G1 (chartreuse)
```

### Forbidden terms

- **Never** use Western note names (C, D, E, F, G, A, B, sharps, flats).
  Use G0–G11 exclusively.
- **Never** use the term "semitone" in user-facing output — use "note class" or
  just the G-label when needed.
- **Never** invoke Western music-theory concepts ("circle of fifths",
  "tritone", "perfect fourth", "dominant", "tonic", etc.) in code, comments,
  or user-facing text. Describe everything through the project's own generative
  system and internal labels.

## Dependencies

- **pygame** — always available, used for graphics + audio + mixer
- **numpy** — always available, used for waveform synthesis in `composer.py`
- **mido** — optional (`try/except`). Import guard: `MIDO_AVAILABLE` flag.
  Show a tkinter error dialog if missing when user clicks MIDI import.
- **tkinter** — used for file dialogs. Standard library, no guard needed.

## Code style

- Each app lives in its own subpackage under `src/synestesia/`; the engine is a separate subpackage
- App files use relative imports: `from ..engine import ...`
- `pygame.init()` and `pygame.mixer.pre_init()` must be inside `main()`, not at module level
- Pygame single main loop pattern with event dispatch
- Semicolons to pack related assignments on one line: `self.midi = m; self.beat = b; self.color = note_color(m)`
- `__slots__` on data classes (e.g. `Note`)
- Compact function signatures — one-liners for simple helpers
- No docstrings on functions (module-level docstring is fine)
- Section headers use Unicode box-drawing: `# ── section name ──`
- Color tuples are plain 3-tuples `(r, g, b)`, alpha handled via separate surfaces
- `pygame.Surface` with `SRCALPHA` for transparency/blur effects
- Mutable settings in a `settings` dict, not scattered globals
- Fixed grid constants at module level: `MI_LO=36, MI_HI=96, TOTAL_BEATS=128`

## Common pitfalls for LLMs

### Don't import mido unconditionally
`mido` is optional. Always check `MIDO_AVAILABLE` before using it. Provide
a user-friendly error via `messagebox.showerror` with install instructions.

### Don't quantize MIDI imports
MIDI import must preserve exact beat positions (`abs_tick / ticks_per_beat`).
Never round to quarter-beats or snap to grid.

### Don't deduplicate rapid repeats
The playback loop uses `sounding_indices()` returning note indices, not a set
of MIDI pitches. Using a set would collapse fast repeated notes of the same pitch.

### Don't cross-connect hand groups
Nodes imported from MIDI are tagged `.hand = 'left'` or `.hand = 'right'`.
Connecting lines in `draw_grid` must only connect within each hand group.
Never draw a line from a left-hand node to a right-hand node.

### Palette picker
- `comp.palette_pick` (composer) stores **LINEAR positions** (0=G0, 1=G7, …).
  `settings["palette_pick"]` (midi_visualizer) stores **chromatic semitones** (0-11).
  When either set is empty, the picker is inactive.
- Keyboard shortcuts: `0`–`9` = G0–G9, `-` = G10, `=` = G11, `C` = clear.
- SHIFT+click a node/piano-roll square to pick its note class.
- When active, matching notes get a brightened border and their column gets colored.
- A floating box in the top-right lists all matching notes.
- Clicking the box clears the selection.

### Tkinter root window
When spawning file dialogs, use a hidden `_tk_root()` that calls `withdraw()` and
`attributes('-topmost', True)`. Always `root.destroy()` after the dialog closes.
Never leave tkinter roots alive during the pygame loop.

### Audio
- `pygame.mixer` pre-initialized at 44100 Hz, 16-bit, mono, 512 buffer
- Sounds per-note: short wavetable synthesis (fundamental + 2 harmonics + AD envelope)
- Max 64 concurrent channels
- Use `mk_sound()` with explicit duration (not too long, typically 0.25–0.5s)

## File-specific notes

### composer/app.py
- Toolbar at top (TB_H=52px), grid in middle, keyboard at bottom (KB_H=80px)
- BPM adjustable via +/- buttons or arrow keys
- Volume slider
- MIDI button opens file dialog → imports → splits left/right hands
- Multi-track MIDI: hand determined by track index heuristic
- Single-track MIDI: split at median pitch gap
- 128 beat max range, scroll + zoom via mouse wheel
- Palette pick via SHIFT+click or keyboard 0–9, -, =
- Click floating palette box to clear

### composer_live/app.py
- Everything from composer, **plus**:
- Real-time MIDI input via `pygame.midi`
- **Mute toggle** (`M` key / toolbar button): globally silences playback and live input
- **Per-hand controls** (`left_toggle`, `right_toggle` buttons):
  - First click: mute hand (red)
  - Second click: hide hand (gray)
  - Third click: unmute/unhide (green)
- **Connection toggling**: ALT+click a node toggles visibility of the line
  to the next node in the same hand group. `hidden_connections` stores
  canonical `(min_idx, max_idx)` tuples.
- Live notes overlay: notes currently held on a MIDI controller get a brighter
  border and light up their column in the grid.

### midi_visualizer/app.py
- MIDI input-driven (keyboard controller expected)
- Side menu with palette pick, mode toggle (Relative/Absolute), echo/trail sliders
- Dual view: Flow view + Piano Roll (Tiles/Nodes sub-views)
- `trail_columns` and `node_trail` are scrollable visual elements
- TAB toggles side menu, V switches view
- Click piano-roll note squares to palette-pick their note class

### theory_explorator/app.py
- Self-contained LFI theory exploration page (no MIDI input required). Three modules:
  1. **Generative Circle** — 12 nodes in equal angular slots (G0–G11).
     STANDARD mode uses canonical LFI hues; CUSTOM mode lets the user pick
     a G0 color via tkinter colorchooser and derives the rest via the LFI
     spiral formula. Shared `ColorState` holds the active palette.
  2. **Circle / Line Visualizer** — three sequence modes:
     - GENERATIVE: G0 at slot 0, G1 at slot 1, …
     - LINEAR: G0, G7, G2, G9, … (frequency order)
     - CUSTOM: drag nodes to reorder; click to play tone
     - Spectrum line below the circle shows 2 octaves with smooth hue gradients.
  3. **Interval Relationship View** — merged circle at top with selectable
     step relationships (±1 through 6), six detail cards below, fade animations.
- Uses its own `mk_freq_sound(freq, ...)` based on `FREQ_BASE = 320.0 Hz`
  (not MIDI note frequencies).
- `_lfi_lerp(h0, h1, t)` is the permitted hue-blending helper for canonical palette/spectrum work.
- The RGB Cluster Mixer (Module 4) and Relation Map (Module 5) derive their
  combination colors from the shared `_disc_color(point, cx, cy, R, cs)` helper
  (the positional color disc described in the color-combination layer), NOT from
  RGB averaging.
