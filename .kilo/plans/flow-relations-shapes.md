# Plan: Flow Relations — Bug Fixes

**Files:** `src/synestesia/midi_visualizer/app.py` (1 change), `src/synestesia/engine/core.py` (3 changes)

---

## Color System (confirmed)

Each step+direction maps to a **single fixed LFI hue** — the hue of the G-class at that generative position. Independent of which notes were pressed.

| Step | Sign | G-class | Hue | Name |
|------|------|---------|-----|------|
| 0 | (same) | G0 | 240.0° | Blue |
| 1 | + | G1 | 90.6° | Chartreuse |
| 1 | − | G11 | 36.5° | Orange |
| 2 | + | G2 | 301.2° | Magenta |
| 2 | − | G10 | 185.9° | Cyan |
| 3 | + | G3 | 151.8° | Spring |
| 3 | − | G9 | 335.3° | Rose |
| 4 | + | G4 | 2.4° | Red |
| 4 | − | G8 | 124.7° | Green |
| 5 | + | G5 | 212.9° | Azure |
| 5 | − | G7 | 274.1° | Violet |
| 6 | ± | G6 | 63.5° | Yellow |

**Computation:** `hue = v_hue(SEM[rel_class][3])`  
Where `rel_class` = `step` if sign is `'+'`, else `(12 - step) % 12`.

**Sub-shapes inherit the parent's sign** — all constituent shapes within a polygon use the same direction as the parent.

---

## Bug 1: Ref/target swapped → wrong step direction
**File:** `app.py`, lines 399-401

Currently `ref` = newest note, `target` = previous. This inverts the step sign.

**Fix:** Restore original: `ref` = first pressed note, `target` = latest pressed note.

```python
# Replace lines 399-401:
if flow_rel_state['target'] is not None:
    flow_rel_state['ref'] = flow_rel_state['target']
flow_rel_state['target'] = new_entry
```

## Bug 2: Convex 12-gon instead of star
**File:** `core.py`, line 1720

`vertices.sort(key=lambda c: _CLASS_TO_LINEAR_POS[c])` reorders to LINEAR positions. For step=1, connecting [G0,G7,G2,G9,...] consecutively = outer convex circle.

**Fix:** Remove the sort. Vertices stay in generative order. Placed at their LINEAR circle positions and connected in that order, they form the correct star polygon for every step (verified for steps 1-5).

## Bug 3: Shape colors from target note instead of step relation
**File:** `core.py`, lines 1716-1717

`v_hue(SEM[target[0]][3])` uses the target note's hue (e.g., G5→Azure for any step). Should use step+direction hue.

**Fix:** Replace with:
```python
rel_class = step if sign == '+' else (12 - step) % 12
ec = _hsl(v_hue(SEM[rel_class][3]), 100, 50)
```

## Bug 4: Sub-shapes use wrong colors (`_STEP_COLORS`)
**File:** `core.py`, lines 1723-1774

All sub-shapes use `_STEP_COLORS` which has arbitrary fixed RGB values that don't match LFI hues.

**Fix:** Replace all sub-shape color references with computed LFI step hues.

### Hexagon skeleton (step=2, lines 1724-1730)
```
Both triangles: color(step=4, sign=parent_sign)
  parent '+' → SEM[4] → G4 → Red
  parent '−' → SEM[8] → G8 → Green
```

### 12-gon decomposition (step=5, lines 1741-1774)
All sub-shapes use the same sign as the parent:

| Sub-shapes | Count | Parent '+' color | Parent '−' color |
|-----------|-------|-----------------|------------------|
| Starburst (step=1) | 1 | G1 Chartreuse | G11 Orange |
| Hexagons (step=2) | 2 | G2 Magenta | G10 Cyan |
| Squares (step=3) | 3 | G3 Spring | G9 Rose |
| Triangles (step=4) | 4 | G4 Red | G8 Green |
| Midpoint lines (step=6) | 6 | G6 Yellow | G6 Yellow |

### Square/Triangle skeleton (step=3,4, lines 1732-1739)
Center-to-edge fan uses the same color as the main outline (already step-based after Bug 3 fix). Remove `_STEP_COLORS` reference.

---

## Summary of changes
| File | Lines | Change |
|------|-------|--------|
| `app.py` | 399-401 | Fix ref/target ordering |
| `core.py` | 1716-1717 | Step-based color instead of target note color |
| `core.py` | 1720 | Remove LINEAR position sort |
| `core.py` | 1723-1774 | Replace `_STEP_COLORS` with LFI step hues |

No new functions needed. The `v_hue(SEM[...][3])` computation is already used throughout the codebase.
