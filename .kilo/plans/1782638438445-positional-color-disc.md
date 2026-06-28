# Plan: Positional color-disc combination method

Replace **RGB-channel averaging** for combination colors with a **positional
color-disc** read. A combination color becomes a pure function of *where* the
combined geometric point sits on the wheel, so any bodies sharing a centroid
share a color (the user's core requirement).

**Applies to:** Module 4 `RGBClusterMixer` AND Module 5 `RelationMap`, in
`src/synestesia/theory_explorator/app.py`. Plus an AGENTS.md doc rewrite.
No engine code changes. No new dependencies.

---

## Core concept (confirmed with user)

- The 12 notes sit on the rim of the wheel at **equal 30° LINEAR slots**
  (top = slot 0), forming a regular 12-gon. Geometry/centroid math is unchanged.
- **Combining N notes = the geometric center of their rim points** (midpoint for
  2, polygon centroid for 3+). This already exists in both modules.
- The combination **color is read from a color disc at that interior point**:
  - **Angle → hue.** Hue varies with the point's angle from the wheel center.
    At any angle, interpolate between the two bracketing rim slots' LFI hues
    using shortest-arc blending (the `_lfi_lerp` idiom). A point exactly on a
    rim node reads that node's exact LFI color.
  - **Radius → saturation/lightness.** `t = distance_from_center / R`. Color =
    `HSL(hue, 100%·t, 50%)`. Rim (`t=1`) = full LFI color; center (`t=0`) =
    mid-gray. `_hsl` already returns gray when `s == 0`.
- **Spiral ≡ circle unification:** LFI hue = `240° + 360°·v mod 360`, which is
  radius-independent and octave-periodic, so the color spiral collapses to a
  single hue circle. The drawing geometry is a *separate* equal-slot circle;
  the bridge is the fixed per-slot hue assignment + shortest-arc interpolation
  for in-between angles. NOTE: hue-by-slot is NOT equally spaced (Pythagorean
  pattern), so geometric angle must be mapped to hue via the rim nodes' actual
  LFI hues, never via raw angle.

### Resulting properties
- Point on a node ⇒ that node's exact LFI color (consistency preserved).
- Pair midpoint ⇒ blend of just those two, muted by how far inward the chord
  midpoint sits.
- **Same centroid ⇒ same color** (the goal). ✔
- Center-symmetric bodies (centroid at center) ⇒ neutral gray (matches the
  AGENTS.md "muted/neutral" language).

---

## Decisions (confirmed)

1. Interior color model = **HSL color disc**: angle→hue, radius→saturation.
2. Angle→hue = **interpolate adjacent rim nodes' LFI hues** (shortest arc), not
   raw angle. Hue source = `ColorState.hue_of(_LINEAR_CHROM[slot])` (live;
   supports standard + custom palettes).
3. Radius→color = **rim full color, center mid-gray**: `HSL(hue, 100%·t, 50%)`.
4. Scope = **both** Module 4 and Module 5.
5. Reference frame = **shared normalized unit disc**: convert each combined
   point to unit-disc coords (relative to that module's own
   `_circle_center_radius()`), then read color from ONE shared disc function.
6. Center edge case: treat tiny radius (`t ≈ 0`) as gray; guard `atan2(0,0)`.
7. AGENTS.md "color-combination layer" section is **rewritten** to make the
   positional disc THE combination method; RGB averaging is retired.

---

## Shared helper to add (module-level, near Module 4 helpers)

A single source of truth used by both modules.

```python
def _disc_color(point, cx, cy, R, cs):
    """Positional color-disc read.
    point  : (x, y) interior point (e.g. midpoint / centroid)
    cx,cy,R: wheel center + rim radius for the SAME 12 equal slots
    cs     : ColorState (live standard/custom hues)
    Returns sRGB tuple. Angle->interpolated LFI hue, radius->saturation,
    rim=full color, center=mid-gray.
    """
    dx, dy = point[0] - cx, point[1] - cy
    d = math.hypot(dx, dy)
    t = max(0.0, min(1.0, d / R)) if R > 0 else 0.0
    if t < 1e-6:
        return _hsl(0.0, 0.0, 50.0)          # center => gray (hue irrelevant)
    # geometric angle, same convention as _circle_point: slot 0 at top
    ang = (math.degrees(math.atan2(dy, dx)) + 90.0) % 360.0   # 0 at slot 0
    slot_f = ang / 30.0                       # 12 slots, 30° each
    s0 = int(slot_f) % 12
    s1 = (s0 + 1) % 12
    frac = slot_f - int(slot_f)
    h0 = cs.hue_of(_LINEAR_CHROM[s0])
    h1 = cs.hue_of(_LINEAR_CHROM[s1])
    diff = ((h1 - h0 + 180.0) % 360.0) - 180.0   # shortest arc
    hue = (h0 + diff * frac) % 360.0
    return _hsl(hue, 100.0 * t, 50.0)
```

Notes:
- Angle convention must match `_circle_point` (`-pi/2 + 2*pi*i/12`, slot 0 at
  top) so a point on slot `i` resolves to `s0 == i, frac == 0` and returns
  exactly `cs.hue_of(_LINEAR_CHROM[i])` at full saturation = that node's color.
- `_circle_point(i)` returns rim points; verify `_disc_color(_circle_point(i,...),
  cx, cy, R, cs) == cs.color(_LINEAR_CHROM[i])` (within rounding) as a sanity
  invariant.

---

## Implementation tasks

### 1. Add the shared helper
- Add `_disc_color(...)` near the Module 4 helpers (after `_polygon_centroid`).
- Keep `_rgb_avg` defined for now ONLY if still referenced; otherwise remove its
  uses (see tasks 2–3). Prefer removing combination uses so RGB averaging is no
  longer the combination method.

### 2. Module 5 `RelationMap` — switch combination colors to disc
Currently each pair/triangle object stores `rgb = _rgb_avg([...])` and triangle
edges are colored by `_pair_color` (RGB avg of two endpoints). Replace with disc
reads using the module's own `_circle_center_radius()`:
- In `_rebuild()`:
  - Pair `rgb` = `_disc_color(midpoint, cx, cy, R, self.cs)`.
  - Triangle `rgb` = `_disc_color(centroid, cx, cy, R, self.cs)`.
  - `hex` recomputed from the new `rgb`.
- Slot draw circle color already uses each object's `rgb` — now disc-derived.
- Revealed triangle:
  - Fill = triangle's disc `rgb` (its actual combination color) at near-solid
    alpha (unchanged behavior, new color source).
  - Edge color of each edge `(a,b)` = `_disc_color(edge_midpoint, cx, cy, R, cs)`
    (the pair combination color of that edge under the new method). Replace the
    `_pair_color`/`_rgb_avg` edge coloring.
- `_pair_color` helper: repoint to `_disc_color(edge_midpoint, ...)` or remove
  and inline.
- Custom palette: since `_disc_color` reads `cs.hue_of` live, colors auto-update;
  still call `_rebuild()`/`_build_slots()` on resize and mode change as today.
- INVARIANT to preserve: triangles sharing a centroid now produce identical
  `rgb` (verify in smoke test).

### 3. Module 4 `RGBClusterMixer` — switch combination colors to disc
Replace RGB-average combination outputs with disc reads using its own
`_circle_center_radius()`:
- `_pair_colors()`: pair `rgb` = `_disc_color(pair_midpoint, cx, cy, R, cs)`
  (compute midpoints from `_circle_point` of the two members).
- `_cluster_color()`: cluster `rgb` = `_disc_color(polygon_centroid_of_selected,
  cx, cy, R, cs)`.
- `_draw_circle()`:
  - Pair relation lines colored by the pair disc color (was `_rgb_avg`).
  - Polygon fill color = cluster disc color (was `_rgb_avg`).
  - Pair midpoint generated circles = pair disc color.
  - Cluster centroid generated circle = cluster disc color.
- `_draw_list()`: pair/cluster swatches + hex use the disc colors (source-note
  rows stay `cs.color(...)`, i.e. LFI palette, unchanged).
- Source-note colors (the 12 rim nodes) remain `cs.color(...)` everywhere — only
  the COMBINATION colors change.

### 4. Clean up RGB-average combination usages
- Remove `_rgb_avg` calls used for combination colors in both modules.
- If `_rgb_avg` becomes unused, remove it; if still used elsewhere, leave it.
- `_polygon_centroid` stays (needed for centroid geometry).

### 5. AGENTS.md rewrite (implementation agent)
Rewrite the "LFI color-combination layer — RGB cluster mixing" section to define
the positional color-disc method:
- 1-1 color = disc color at the chord midpoint.
- Cluster/triangle color = disc color at the polygon centroid.
- Angle→interpolated LFI hue (shortest arc between bracketing rim slots),
  radius→saturation (`HSL(hue, 100%·t, 50%)`), rim=full color, center=gray.
- State that geometrically-equivalent bodies (same centroid) now share a color
  by construction.
- Retire/deprecate the equal-part RGB-average rule; note the canonical
  sound→light palette for the 12 source notes is still hue-derived and is NEVER
  RGB-interpolated.
- Keep `GeneratedColor` shape; `rgb`/`hex` now come from the disc.

---

## Validation

- `python -m pytest tests/ -v` — must stay green (pure-math; no engine change).
- Headless smoke (SDL dummy drivers), assert:
  1. `_disc_color(_circle_point(i,cx,cy,R), cx,cy,R, cs)` ≈ `cs.color(
     _LINEAR_CHROM[i])` for all 12 i (rim invariant), standard palette.
  2. Two triangles sharing a centroid (e.g. previously-divergent
     `(0,1,4)` vs `(2,3,11)` slot triples) now yield identical `rgb`.
  3. A center-symmetric body (centroid at wheel center, e.g. step-6 / step-2
     full ring) yields near-gray.
  4. Repeat invariant (1) under a custom palette (`cs.set_custom(...)`).
  5. `draw()` runs without error for all modes in both modules.
- Manual: `python menu.py` → Theory Explorator → CLUSTER MIXER and RELATION MAP.

---

## Risks / notes

- **Angle convention mismatch** is the main correctness risk: `_disc_color`'s
  `atan2`→slot mapping MUST match `_circle_point` so the rim invariant holds.
  The +90° offset and `/30°` slotting encode this; verify with smoke test (1).
- **Hue interpolation direction:** use shortest-arc (`_lfi_lerp` math) so the
  blend rides the color circle correctly across the 360°/0° seam.
- **Muting is expected:** combination colors are now generally less saturated
  than before (interior points have `t < 1`). This is intended, not a bug.
- **Doc/code drift:** AGENTS.md and code must land together; plan task 5 is
  required, not optional.
- **No engine edits.** If engine changes seem needed, stop and reassess.
- Planning agent edits only this plan file; an implementation-capable agent makes
  the code + AGENTS.md edits.
