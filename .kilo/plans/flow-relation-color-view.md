# Plan: Flow Relation Color View

## 1. Overview

Split the current FLOW tab in the MIDI Visualizer into two sub-tabs:
- **NOTE COLOR** — existing view (colored vertical panels per held note)
- **RELATION COLOR** — new interactive note circle view.

The circle displays generative step operations as inscribed geometric shapes.
Each shape is colored with the **LFI hue of the target note's G-class** — not
arbitrary red/green. The ±4 triangle example happens to be red/green because
G4 is red and G8 is green in the LFI system; every other operation pair has
its own distinct LFI color.

## 2. Structure Changes

### Top-level tabs remain: FLOW | PIANO ROLL

### FLOW gains sub-tabs (same style as PIANO ROLL sub-tabs):
```
FLOW:  [ NOTE COLOR ]  [ RELATION COLOR ]
```

Sub-tab bar sits at y=VIEW_TAB_H, height=SUB_TAB_H, just like the Piano Roll
sub-tab bar.

### Variables to add in `midi_visualizer/app.py`:
```
flow_sub = 0        # 0 = note color, 1 = relation color
flow_rel_state = None   # dict with ref/target note info + computed step + fade
```

## 3. Fixed Circle Labels

The 12 LINEAR sequence positions (clockwise from top) get fixed operation
labels. These describe the generative operation needed to go from G0 at the
top to each position. Labels never change when the reference moves.

| Clockwise pos | LINEAR class | Label |
|---------------|-------------|-------|
| 0 (top)       | G0          | 1 (R) |
| 1             | G7          | -5    |
| 2             | G2          | +2    |
| 3             | G9          | -3    |
| 4             | G4          | +4    |
| 5             | G11         | +1    |
| 6 (bottom)    | G6          | -R    |
| 7             | G1          | -1    |
| 8             | G8          | -4    |
| 9             | G3          | +3    |
| 10            | G10         | -2    |
| 11            | G5          | +5    |

## 4. Interaction Logic

### State: `flow_rel_state`
```python
flow_rel_state = {
    'ref': None,       # (g_class, midi_note, color, label, circle_pos)
    'target': None,    # (g_class, midi_note, color, label, circle_pos)
    'step': 0,         # 0 = same note (octave), 1-6 = generative step count
    'sign': '',        # '+' / '-' / '-R' / ''
    'fade_alpha': 0.0, # animated fade for polygon
}
```

### MIDI press handling (when `flow_sub == 1`):
1. **First press ever** → set `ref`, clear `target`. Show small blue
   inscribed circle (octave +0, G0's Blue at 240°).
2. **Same note-class as ref** (any octave) → keep `ref`, clear `target`.
   Show small blue circle (step=0).
3. **Different note-class from ref** → shift: old `target` → `ref`,
   new note → `target`. Compute step and sign between `ref` and `target`.
   Draw inscribed polygon colored with the **target note's LFI hue**.

### Relation computation:
```
fwd = (target_g_class - ref_g_class) % 12   # steps forward (G+)
bwd = (ref_g_class - target_g_class) % 12   # steps backward (G-)
if fwd == 6 and bwd == 6: step=6, sign='-R'
elif fwd <= bwd:           step=fwd, sign='+'
else:                      step=bwd, sign='-'
```

### Shape mapping:
| Step | n_sides | Shape              |
|------|---------|--------------------|
| 0    | —       | inscribed blue circle (see §5.3) |
| 1    | 12      | starburst (12 radial lines)     |
| 2    | 6       | hexagon             |
| 3    | 4       | square              |
| 4    | 3       | triangle            |
| 5    | 12      | 12-gon              |
| 6    | 2       | midpoint line (diameter through ref) |

### Color: always the LFI hue of the target note's G-class

The target note's G-class determines the color via `v_hue(SEM[g_class][3])`.
This inherently captures the specific operation's color identity since each
operation pair maps to a specific note class:

| Operation (from G0) | Target G-class | LFI hue   | Color |
|---------------------|----------------|----------|-------|
| R / +0              | G0             | 240°     | Blue  |
| -5                  | G7             | 274°     | Violet |
| +2                  | G2             | 301°     | Magenta |
| -3                  | G9             | 335°     | Rose |
| +4                  | G4             | 2°       | Red |
| +1                  | G11            | 36°      | Orange |
| -R                  | G6             | 64°      | Yellow |
| -1                  | G1             | 91°      | Chartreuse |
| -4                  | G8             | 125°     | Green |
| +3                  | G3             | 152°     | Spring |
| -2                  | G10            | 186°     | Cyan |
| +5                  | G5             | 213°     | Azure |

When the reference changes (e.g. ref=G4, target=G1), the step count is
computed relative to the new ref, but the **color still comes from the
target note's G-class** (so G1 → chartreuse, regardless of what the ref is).

## 5. Visual Rendering (`draw_flow_relations` in `engine/core.py`)

### 5.1 Circle layout
- Same circle diameter and layout as the Piano Roll Relations circle
- 12 node positions at equal angles, LINEAR sequence order (G0 at top)
- Each node displays its **fixed operation label** (see §3)
- Nodes **do not** show LFI colors — only the shapes do
- Held note positions get a white highlight ring and brighter label text
- Ref position: brighter ring + small solid dot
- Target position: ring of the target's LFI color

### 5.2 Reference and target highlights
- **ref note position**: bright white circle ring (radius + 4px) + solid dot
- **target note position**: ring in the target's LFI color (radius + 3px)
- When a note is held and matches a circle position, its node gets a soft
  blink effect

### 5.3 Blue inscribed circle (step=0 / octave +0)
- Same center as the main note circle, radius ≈ 35-40% of main circle radius
- Filled with G0's canonical Blue (#0000ff, 240°), semi-transparent (alpha ~120)
- Thin white border ring
- Rendered behind the main circle's node labels so they stay readable

### 5.4 Inscribed polygons (step 1-6)

Polygon is a regular n-gon inscribed in the main circle, with **one vertex
at the reference note's position**.

**Rendering**:
- Compute `lin_geo = min(fwd, bwd)` (the step count used for polygon stepping)
- `n_sides = 12 // gcd(lin_geo, 12)`
- Build vertex list by stepping `lin_geo` positions around the circle
  starting from ref's position, following the shorter arc direction
- Draw all polygon edges as lines with alpha
- Draw the active chord edge (ref→target) with brighter alpha
- Fill interior with very low alpha (α≈30)
- Mark the ref vertex with a small solid dot

**Colors**: all polygon edges use the **target note's LFI hue** at full
saturation and 50% lightness (via `_hsl(target_hue, 100, 50)`) with
per-edge alpha. The active chord edge uses higher alpha (≈200), other
edges use lower alpha (≈100).

**Special cases**:
- Step 0 (blue circle): drawn before polygons
- Step 6 (midpoint): a single diameter line through ref's position,
  colored with the target's LFI hue, plus a small dot at each endpoint
- Step 1 (starburst): 12 short radial lines from each vertex toward center,
  coloring each with its own LFI hue (since step 1 visits all 12 classes)

### 5.5 Info panel (below the circle)
- G-class labels for ref and target: "REF: G{ref_class}" / "TARGET: G{target_class}"
- Relation description: "+4 Triangles", "-2 Hexagons", "-R Midpoint", etc.
- Target's LFI color shown as a small swatch
- Positioned below the circle, centered

### 5.6 Fade animation
- When the relation changes (new target with different step), `fade_alpha`
  resets to 0.0 and ramps to 1.0 over ~0.3s
- `fade_alpha` multiplies all polygon edge/fill alphas
- When step=0 (octave circle), fade still applies for smooth transition

## 6. Files to Modify

### `src/synestesia/engine/core.py`
1. Add constant `FLOW_REL_LABELS`: list of 12 fixed labels
   `["1 (R)", "-5", "+2", "-3", "+4", "+1", "-R", "-1", "-4", "+3", "-2", "+5"]`
2. Add `draw_flow_sub_tabs(surface, fonts, content_x, content_w, flow_sub)`
   — sub-tab bar for FLOW, exact same style as `draw_piano_roll_sub_tabs`
   but with labels ["NOTE COLOR", "RELATION COLOR"]
3. Add `draw_flow_relations(surface, fonts, flow_rel_state, note_states,
   content_x, content_w, W, H, bg)` — main rendering function containing:
   - Circle with 12 nodes and fixed labels
   - Blue inscribed circle (when step=0)
   - Inscribed polygon (when step 1-6)
   - Info panel below
   - Fade animation support

### `src/synestesia/engine/__init__.py`
4. Export `draw_flow_sub_tabs` and `draw_flow_relations`

### `src/synestesia/midi_visualizer/app.py`
5. Add `flow_sub = 0` variable
6. Add `flow_rel_state` initialization dict
7. Mouse click handler: detect clicks on flow sub-tab bar when `view_tab == 0`
8. Keyboard shortcut `B` to toggle `flow_sub`
9. MIDI input handler: when `view_tab == 0 and flow_sub == 1`, manage
   `flow_rel_state` (ref/target tracking, step computation, fade reset)
10. Per-frame update: lerp `fade_alpha` toward target (0.0 or 1.0)
11. Render path: when `view_tab == 0`:
    - Draw `draw_flow_sub_tabs`
    - `flow_sub == 0` → existing note color panels (same as now)
    - `flow_sub == 1` → call `draw_flow_relations`

## 7. Edge Cases

- **No MIDI notes held**: idle state — circle with all labels visible,
  no shapes, no highlights, "play a note..." hint
- **Note released while being ref/target**: state persists until a new
  note-on event arrives (ref and target stay in `flow_rel_state`)
- **Rapid repeated notes (same class)**: step stays 0, blue circle shown
- **Three rapid different notes**: latest two become ref/target pair
- **Window resize**: circle and labels scale with available space
- **Menu open/closed**: content_x shifts by MENU_W as usual
- **Switching from RELATION COLOR to NOTE COLOR and back**: state preserved

## 8. Keyboard Shortcuts Summary

| Key | Action |
|-----|--------|
| TAB | toggle side menu |
| V   | switch top-level view (FLOW ↔ PIANO ROLL) |
| B   | switch FLOW sub-tab (NOTE COLOR ↔ RELATION COLOR) |
| ESC | quit |

## 9. Notes

- The existing `_LINEAR_SEQ` and `_CLASS_TO_LINEAR_POS` helpers in core.py
  already exist and can be reused for the circle layout
- The polygon vertex computation reuses the same gcd-based logic already
  in `draw_piano_roll_relations`
- No new dependencies needed — only pygame, math, and the existing LFI engine
