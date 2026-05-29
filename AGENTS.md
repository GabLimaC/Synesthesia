# Synesthesia Project Conventions

## Project overview

Three interactive tools for MIDI visualization and composition, all using the
**Liminal Flow Intonation (LFI)** color system — not Western 12-tone theory.

### Applications (canonical source in `src/synestesia/`)

- **`src/synestesia/composer/app.py`** — piano-roll node-based composer with MIDI import/playback
- **`src/synestesia/composer_live/app.py`** — composer + real-time MIDI input, hand mute/hide, connection toggling
- **`src/synestesia/visualizer/app.py`** — MIDI visualizer (Flow view + Piano Roll Tiles/Nodes)

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
│       └── visualizer/
│           ├── app.py
│           └── __init__.py        # exposes run()
├── tests/
│   └── test_lfi.py                # Pure-math tests (no display required)
├── README.md
├── requirements.txt
├── pyproject.toml
└── AGENTS.md
```

### Legacy files (project root)

The original flat scripts (`engine.py`, `composer.py`, `composer_live.py`,
`synestv2.py`, `synesthesia.py`) remain at the root for reference. The
canonical source of truth is `src/synestesia/`.

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

```
LFI_DATA layout: (semitone_index, name, frequency, v_value)
  0 = G0    4 = G4     8 = G8
  1 = G1    5 = G5     9 = G9
  2 = G2    6 = G6    10 = G10
  3 = G3    7 = G7    11 = G11
```

  - `name(midi)` returns e.g. `"G43"` (G4 in octave 3), `"G70"` (G7 in octave 0)
  - The `v` value (4th tuple element) determines the hue via `v_hue(v)`
  - Octave lightness is modulated by octave height in `note_color()`

### The generative system

The 12 note classes are produced by two generative operators applied to a
starting reference:

- **G+** — multiply frequency by `3/2`
- **G-** — multiply frequency by `4/3`

Starting from any reference, repeated application of G+ and G- (with octave
reduction to keep ratios within [1, 2)) produces the 12 distinct classes.
This is a **frequency-agnostic** mathematical system; it does not depend on any
external tuning standard.

The generative sequence, when laid out as frequency ratios inside one octave,
produces the **Linear sequence**:

`G0 → G7 → G2 → G9 → G4 → G11 → G6 → G1 → G8 → G3 → G10 → G5`

After 12 steps the cycle closes (one octave above the starting pitch class).

### G6 — the structural midpoint

In the Linear sequence, **G6 is the 6th step**. Its frequency ratio is the
logarithmic midpoint of the octave — approximately √2 (~1.414). This makes G6
the point of **maximum distance** from G0 within the octave: the structural
opposite of the root.

In Western terminology this interval is called the tritone. That label is
**forbidden** in this project; describe it only as the structural midpoint or
logarithmic opposite of G0.

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
- Anchor 240° = pure bright Blue (G0).
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

| G+^n | reduced ratio | log₂ frac | hue (°) | hex (HSL→sRGB, S=1 L=0.5) |
|------|---------------:|----------:|--------:|---------------------------:|
| G+^0 | 1.000000       | 0.000000  | 240.00° | #0000ff (Blue)             |
| G+^1 | 1.500000       | 0.584963  |  90.59° | #7dff00 (Chartreuse)       |
| G+^2 | 1.125000       | 0.169925  | 301.17° | #ff00fa (Magenta)          |
| G+^3 | 1.687500       | 0.754888  | 151.76° | #00ff87 (Spring Green)     |
| G+^4 | 1.265625       | 0.339850  |   2.35° | #ff0a00 (Red)              |
| G+^5 | 1.898438       | 0.924813  | 212.93° | #0073ff (Azure)            |
| G+^6 | 1.423828       | 0.509775  |  63.52° | #f0ff00 (Yellow)           |
| G+^7 | 1.067871       | 0.094738  | 274.11° | #9100ff (Violet)           |
| G+^8 | 1.601807       | 0.679700  | 124.69° | #00ff14 (Green)            |
| G+^9 | 1.201355       | 0.264663  | 335.28° | #ff0069 (Rose)             |
| G+^10| 1.802032       | 0.849625  | 185.87° | #00e6ff (Cyan)             |
| G+^11| 1.351524       | 0.434588  |  36.45° | #ff9b00 (Orange)           |
| G+^12| 1.013643       | 0.019550  | 247.04° | #1e00ff (near Blue — comma) |

...and so on.

Continue with the rest of the original file content (Frequency reference etc.)
### Frequency reference ("canonical" values)

When a base frequency is needed, the **canonical reference** is:

- **G0 = 20 Hz** (minimum)
- **Maximum G0 in the system = 20 480 Hz** (10 natural octaves above the base)

These are power-of-two bounds. The word **"canonical"** is acceptable when it
refers specifically to this base-frequency convention. It is a technical term
of the project, not a forbidden word.

In practice the code uses `F_BASE = 40.0 Hz` and `F_TOP = 10240.0 Hz` for
real-world instrument compatibility; the canonical values remain the theoretical
reference frame.

### MIDI compatibility convention

For compatibility with real MIDI instruments, the project accepts the mapping
**C1 = G01** (Western MIDI note 12 maps to G0 in octave 1). The implementation
allows switching between this practical convention and the internal LFI numbering.

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
- `comp.palette_pick` stores a semitone index (0–11), or `None` when inactive
- SHIFT+click a node to pick its note class
- When active, matching notes get a brightened border and their column gets colored
- A floating box in the top-right lists all matching notes
- Clicking the box clears the selection

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

### composer.py
- Toolbar at top (TB_H=52px), grid in middle, keyboard at bottom (KB_H=80px)
- BPM adjustable via +/- buttons or arrow keys
- Volume slider
- MIDI button opens file dialog → imports → splits left/right hands
- Multi-track MIDI: hand determined by track index heuristic
- Single-track MIDI: split at median pitch gap
- 128 beat max range, scroll + zoom via mouse wheel

### synesthesia.py / synestv2.py
- MIDI input-driven (keyboard controller expected)
- Side menu with palette pick, mode toggle, echo/trail sliders
- synestv2 has dual view: Flow view + Piano Roll (Tiles/Nodes sub-views)
- trail_columns and node_trail are scrollable visual elements