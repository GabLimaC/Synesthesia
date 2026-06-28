# Plan: Relation Map tab (theory_explorator)

Add a new 5th tab to `src/synestesia/theory_explorator/app.py` that maps **all**
pairwise (1-to-1) and triple (triangle) LFI relations as RGB-combination color
circles. Lines/triangles are hidden by default; clicking a generated circle
plays its member notes together and reveals its geometry. A view-mode selector
chooses which relation set is shown.

This is a NEW tab. The existing selection-driven `RGBClusterMixer` (Module 4,
"CLUSTER MIXER") stays unchanged.

**File touched:** `src/synestesia/theory_explorator/app.py` only. No engine
changes. No new dependencies.

---

## Concepts / decisions (confirmed with user)

- **Geometry & order:** 12 source nodes placed on the equally-spaced circle in
  **LINEAR** order (`_LINEAR_CHROM = [0,7,2,9,4,11,6,1,8,3,10,5]`), slot 0 at top
  (reuse `_circle_point` math from `RGBClusterMixer`). Members are stored as
  **LINEAR positions** (0..11), labels as `G{_LINEAR_CHROM[pos]}`.
- **Color:** combination colors use equal-part RGB average (`_rgb_avg`) of the
  source G-class sRGB colors, per the AGENTS.md color-combination layer. Source
  colors themselves come from the LFI palette via `ColorState` (standard or
  custom). RGB averaging is only for the combination layer.
- **Pair set:** all C(12,2) = 66 pairs.
- **Triangle set:** all C(12,3) = 220 triangles. A triangle is `trimmed` when
  **all three** of its edges have circular distance >= 3 on the 12-slot LINEAR
  circle, where edge distance = `min(d, 12 - d)` of the two members' LINEAR
  positions. (Example: G0 at pos 0, G9 at pos 3 -> distance 3 -> allowed.)
- **View modes** (control-bar buttons; default = `1-to-1`):
  1. `1-to-1` — show all 66 pair-midpoint circles.
  2. `TRIMMED TRI` — show triangle-centroid circles where `trimmed` is true.
  3. `FULL TRI` — show all 220 triangle-centroid circles.
  4. `TRIMMED TRI + 1-to-1` — show trimmed triangle circles + all pair circles.
- **Layout:** full-width content area for the circle (NO side color-list panel).
- **Reveal interaction:** clicking a generated circle TOGGLES its geometry
  reveal (line for a pair, triangle outline for a triple). Multiple reveals
  persist simultaneously. Each click (re)plays the member notes together. A
  `CLEAR` button hides all reveals.
- **Source nodes:** always shown and clickable; clicking one plays that single
  note's tone.
- **No Western terms** anywhere (labels G0-G11 only).

---

## Data model

Add a relation-object builder. Each object follows the AGENTS.md
`GeneratedColor` shape, extended with `point` (draw location) and `geometry`.

Pair object:
```python
{"kind": "pair",
 "members": [lin_a, lin_b],           # LINEAR positions
 "labels":  ["G..", "G.."],
 "rgb": (r,g,b), "hex": "#rrggbb",
 "point": (mx, my),                   # midpoint of the chord
 "geometry": ("line", a_pt, b_pt)}
```

Triangle object:
```python
{"kind": "triangle",
 "members": [lin_a, lin_b, lin_c],    # sorted LINEAR positions
 "labels":  ["G..","G..","G.."],
 "rgb": (r,g,b), "hex": "#rrggbb",
 "point": (cx, cy),                   # polygon centroid (_polygon_centroid)
 "geometry": ("triangle", [pt_a, pt_b, pt_c]),
 "trimmed": bool}                     # all 3 edges circular-distance >= 3
```

Helpers to reuse (already in file, Module 4 section): `_rgb_avg`, `_rgb_hex`,
`_polygon_centroid`, `_LINEAR_CHROM`, `_LINEAR_POS_OF`, `NOTE_FREQS`,
`mk_freq_sound`.

Edge-distance helper (new, small):
```python
def _circ_dist(p, q):
    d = abs(p - q) % 12
    return min(d, 12 - d)
```

`members`/`point`/`geometry` depend on circle center+radius, so build them in a
method that runs on init, on `resize`, and whenever the palette changes
(standard/custom toggle). Colors (`rgb`/`hex`) depend on `ColorState`; recompute
colors each frame is cheap, but precomputing geometry once per layout and colors
on rebuild is preferred. Simplest robust approach: rebuild the full object lists
in `resize()` and also when the active color mode may have changed (rebuild on
each `draw` is acceptable since 286 averages are trivial, but prefer caching and
rebuilding on resize + a cheap palette-change check).

---

## New class: `RelationMap`

Model after `RGBClusterMixer` for layout/event conventions.

Constructor: `__init__(self, rect, fonts, color_state)` storing
`self.rect, self.fonts, self.cs`, plus:
- `self.mode = 0` (0=1-to-1, 1=trimmed tri, 2=full tri, 3=trimmed tri + 1-to-1)
- `self.revealed = set()` of object keys currently revealed.
- `self.sounds = {}` lazy per-note `Sound` cache (like Module 4's
  `_ensure_sounds`/`_play`).
- `self._hovered = None` (currently hovered generated circle key).
- `self._last_click_info = None` + tick, for the floating readout.
- `self._pairs`, `self._triangles` built via `_rebuild()`.

Object key: a hashable id, e.g. `("pair", a, b)` or `("tri", a, b, c)`.

### Methods
- `resize(rect)` -> set rect, rebuild buttons, `_rebuild()`.
- `_ctrl_rect()` -> control bar (height `CTRL_H`).
- `_content_rect()` -> area below control bar (full width).
- `_circle_center_radius()` -> center + radius from `_content_rect()` (reuse the
  `RGBClusterMixer` proportions but using full width).
- `_circle_point(i, cx, cy, r)` -> same formula as Module 4.
- `_palette()` -> `[self.cs.color(_LINEAR_CHROM[n]) for n in range(12)]`.
- `_build_buttons()` -> `CLEAR` button + 4 mode buttons in the control bar.
- `_rebuild()` -> recompute `self._pairs` and `self._triangles` (geometry +
  colors) from current center/radius and palette.
- `_visible_objects()` -> list of objects for the active mode:
  - mode 0: pairs
  - mode 1: triangles where `trimmed`
  - mode 2: all triangles
  - mode 3: trimmed triangles + pairs
- `_ensure_sounds()` / `_play_notes(linear_positions)` -> for each member,
  `self.sounds[g_class].stop(); .play()` so they sound simultaneously
  (`g_class = _LINEAR_CHROM[pos]`, freq via `NOTE_FREQS[g_class]`).
- `_hit_generated(pos)` -> nearest visible generated circle within a hit radius
  (handle overlap: choose the closest `point` within e.g. `GEN_R + 4` px).
- `_hit_source(pos)` -> source node index within `SOURCE_NODE_R + 3`.
- `draw(surf)`:
  1. `COMP_BG` fill, control bar + title (`RELATION MAP`), CLEAR + mode buttons.
  2. ring + draw revealed geometry first (lines/triangle outlines colored by
     each revealed object's `rgb`; triangle reveals may use a light translucent
     fill via an `SRCALPHA` surface like Module 4's polygon fill).
  3. draw all visible generated-color circles at their `point` (small filled
     circle + dark outline; hovered = brighter/thicker outline).
  4. draw 12 source nodes + `G{n}` labels on top.
  5. floating readout (top of content) for last clicked object: labels, hex,
     and member frequencies; fade after ~1.5s (reuse the active-tick fade idiom).
  6. bottom hint line: "click circle = play + toggle reveal · click node = tone".
  7. `DIVIDER_COL` border.
- `handle_event(event)`:
  - `MOUSEBUTTONDOWN` left: CLEAR button -> `self.revealed.clear()`; mode
    buttons -> set mode (+ keep `revealed` or clear it — clear on mode change to
    avoid revealing hidden-mode geometry); generated circle hit -> toggle its
    key in `revealed`, `_play_notes(members)`, set readout; else source hit ->
    `_play_notes([pos])`, set readout.
  - `MOUSEMOTION`: update button hovers + `self._hovered` (nearest visible
    generated circle).
  - `KEYDOWN`: optional `C` to clear reveals (consistent with Module 4).
- `update(dt)` -> no-op (or advance readout fade if time-based).

### New module-level constants (Relation Map section)
```python
RM_GEN_R       = 6    # generated-color circle radius
RM_REVEAL_W    = 2    # revealed line/triangle stroke width
RM_TRI_ALPHA   = 28   # translucent triangle fill when revealed
```
(Reuse existing `SOURCE_NODE_R`, `RING_COL`, etc.)

---

## Wiring in `main()` and tab bar

- `_draw_view_tab_bar`: append `"RELATION MAP"` -> `labels` becomes 5 entries;
  `n = len(labels)` already generalizes; `tab_w = w // n`.
- `_hit_view_tab`: change `(mx * 4) // w` to `(mx * 5) // w` (or derive from a
  shared tab count constant to avoid the magic number).
- `_make_content_rect` unchanged.
- In `main()`: construct `comp5 = RelationMap(rect, fonts, cs)`.
- Add `comp5.resize(rect)` in the `VIDEORESIZE` branch.
- Add event dispatch for `active_tab == 4` in every place `comp4` is dispatched
  (KEYDOWN, generic else, MOUSEBUTTONDOWN-non-tab, trailing else).
- Add `elif active_tab == 4: comp5.draw(screen)` in the draw section (and adjust
  the current `else` that draws `comp4` so tab 3 -> comp4, tab 4 -> comp5).
- If `RelationMap` needs animation later, call `comp5.update(dt)` (optional now).

---

## Implementation order (for the implementer)

1. Add Relation Map constants + `_circ_dist` helper near the Module 4 helpers.
2. Implement `RelationMap` class after `RGBClusterMixer`.
3. Update `_draw_view_tab_bar` labels and `_hit_view_tab` divisor.
4. Wire `comp5` into `main()` (construct, resize, all event branches, draw).
5. Manual run + sanity check.

---

## Validation

- `python -m pytest tests/ -v` — must stay green (pure-math tests; no display).
  No engine/math changes, so this should be unaffected.
- `python menu.py` -> Theory Explorator -> RELATION MAP tab:
  - Default mode shows 66 pair circles, no lines.
  - Switching modes shows trimmed/full triangle circles correctly; trimmed set
    excludes any triangle with an edge of circular distance < 3.
  - Clicking a source node plays one tone.
  - Clicking a generated circle plays its 2 or 3 notes together and toggles its
    line/triangle reveal; multiple reveals persist; CLEAR hides all.
  - Custom-color mode (Module 1) changes propagate to source + combination
    colors after rebuild.
  - Window resize repositions everything (rebuild on `VIDEORESIZE`).

---

## Risks / notes

- **Visual density:** FULL TRI = 220 centroid circles overlap heavily. Mitigate
  with nearest-circle-within-radius hit testing and a small `RM_GEN_R`. This is
  expected/acceptable per the design.
- **Performance:** 286 RGB averages + draws per frame is trivial for pygame at
  60 FPS; safe to rebuild colors on palette change rather than every frame.
- **Conventions:** keep LINEAR positions for `members`, G-labels only, never
  Western note names or forbidden theory terms; RGB averaging strictly for the
  combination layer (source colors stay LFI-derived).
- **No engine edits**; if the implementer finds engine changes are required,
  stop and switch to an implementation-capable agent.
