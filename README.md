# Synesthesia

Three interactive tools for MIDI visualization and composition using the
**Liminal Flow Intonation (LFI)** color system — a frequency-derived, logarithmic
spiral mapping of sound to light. Hue is computed directly from `log₂(frequency)`;
no Western music theory is used.

## Applications

| App | Description |
|-----|-------------|
| **Composer** | Piano-roll node editor with MIDI import and playback |
| **Composer Live** | Composer + real-time MIDI input, per-hand mute/hide, connection toggling |
| **Visualizer** | Real-time MIDI visualizer — Flow view + Piano Roll (Tiles / Nodes) |

## Quick start

```bash
# Install dependencies
pip install pygame numpy mido

# Launch the menu
python menu.py
```

Then enter `1`, `2`, or `3` to open an application.

## Project structure

```
synestesia/
├── menu.py                       # Launcher — choose which app to run
├── src/
│   └── synestesia/
│       ├── engine/               # LFI model layer (color, audio, MIDI, drawing)
│       │   ├── core.py           # All shared logic
│       │   └── __init__.py       # Re-exports everything from core
│       ├── composer/             # Piano-roll composition tool
│       │   └── app.py
│       ├── composer_live/        # Composer + live MIDI
│       │   └── app.py
│       └── visualizer/           # Real-time MIDI visualizer (synestv2)
│           └── app.py
├── tests/
│   └── test_lfi.py               # Pure-math tests for the LFI engine
└── AGENTS.md                     # Project conventions for AI agents
```

Legacy root-level scripts (`engine.py`, `composer.py`, `composer_live.py`,
`synestv2.py`, `synesthesia.py`) are kept for reference; the canonical source
of truth is now `src/synestesia/`.

## LFI color system

The color mapping is derived from a logarithmic spiral over frequency:

```
hue(r) = (240° + 360° × log₂(r)) mod 360°
```

- `r` = frequency ratio reduced to `[1, 2)`
- Anchor: G0 = 240° (Blue)
- G+ operator (×3/2) moves hue by ≈ 210.587°
- After 12 G+ steps: near-closure with a ≈ 7.04° gap (the Pythagorean comma)

The 12 note classes G0–G11 are not Western note names. They label positions
in a self-contained generative sequence.

## Dependencies

| Package | Required | Notes |
|---------|----------|-------|
| `pygame` | Yes | Graphics, audio, MIDI I/O |
| `numpy` | Yes | Wavetable synthesis |
| `mido` | Optional | MIDI file import (`.mid`) |

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

The tests cover the LFI math (color derivation, anchor table, Pythagorean comma)
and require no display — pygame is stubbed out.

## Controls

### Composer / Composer Live

| Input | Action |
|-------|--------|
| Left-click grid | Place note |
| SHIFT+click node | Palette-pick its note class |
| Right-click node | Delete |
| Drag node | Move |
| CTRL+drag | Pan canvas |
| Mouse wheel | Scroll |
| CTRL+wheel | Zoom |
| SPACE | Play / Pause |
| R | Reverse |
| S | Stop & reset |
| ↑ / ↓ | BPM ±5 |
| M | Mute (Composer Live) |
| 0–9, -, = | Palette pick G0–G11 |
| C | Clear palette |
| ESC | Quit |

### Visualizer

| Input | Action |
|-------|--------|
| TAB | Toggle side menu |
| V | Switch view (Flow / Piano Roll) |
| ESC | Quit |
