# Plan: Keyboard Relation View

**New tab in MIDI Visualizer** — shows piano keys labeled by their LFI relation (shape + color) to a pressed reference note.

---

## Overview

A third main tab **"KEYBOARD"** added to the MIDI Visualizer, alongside the existing FLOW and PIANO ROLL tabs. When a MIDI note is pressed, it becomes the reference **R** (blue). Every other visible key is relabeled to show:

- Its **generative step & direction** relative to R (±1 through ±5, or 6)
- The corresponding **geometric shape** (starburst, hexagon, square, triangle, 12-gon, midpoint)
- The **LFI hue** of that relation (computed from the fixed step→hue mapping already in the engine)

---

## Layout

```
┌─────────────────────────────────────────┐
│  [FLOW]  [PIANO ROLL]  [KEYBOARD]  [V] │  ← 3-tab view bar
├─────────────────────────────────────────┤
│                                         │
│       RELATION SHAPE VISUALIZER         │  ← top ~40%
│    (inscribed polygon, LFI gradient)    │
│       e.g. "±3 Squares  ← CCW"         │
│                                         │
├─────────────────────────────────────────┤
│                                         │
│    2-OCTAVE PIANO KEYBOARD              │  ← bottom ~60%
│    MIDI 48–71, centered on G0 (60)      │
│                                         │
│  ┌─┐ ┌─┐  ┌─┐ ┌─┐ ┌─┐  ┌─┐ ┌─┐       │
│  │+1│ │-3│  │+4│ │-1│ │+5│  │±0│ │-5│  ...│
│  └─┘ └─┘  └─┘ └─┘ └─┘  └─┘ └─┘       │
│  ┌───┐┌───┐ ┌───┐┌───┐ ┌───┐┌───┐     │
│  │G7 ││G9 │ │G11││G6 │ │G8 ││G10│     │  ← black keys
│  └───┘└───┘ └───┘└───┘ └───┘└───┘     │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬──┐│
│  │ G0  │ G2  │ G4  │ G1  │ G3  │ G5  │..││  ← white keys
│  │ BLUE│±2◆ │±4▲ │-1✦ │±3■ │±5◎ │..││
│  └─────┴─────┴─────┴─────┴─────┴─────┴──┘│
└─────────────────────────────────────────┘
```

### Top: Relation Shape Visualizer
- Shows the **geometric polygon** for the relation between the last two different notes pressed
- Uses the same inscribed-polygon drawing logic already in `draw_flow_relations()`
- LFI gradient-colored edges, sub-shapes outlined
- Step name + direction displayed below (e.g. "±3 Squares ← CCW")
- If only one note pressed: blue circle (octave/same-class indicator)
- If no notes: idle "play a note..." hint

### Bottom: Piano Keyboard
- **2 octaves**: MIDI notes 48 through 71 (24 chromatic keys, G0 at center)
- White keys drawn as wider rectangles, black keys as narrower raised rectangles
- Each key is labeled with:
  - **G-class** (G0–G11)
  - **Relation label** (±1 through ±5, or 6, or "R" for reference)
  - **Background tint** using the relation's LFI hue
- Reference note keys (all octaves) are highlighted **blue**
- Pressed keys get a bright border bloom

---

## Step → Shape → Color mapping (already in engine)

Uses the existing `_compute_generative_step()` and relation system:

| Step | Direction | G-class | Hue       | Shape       |
|------|-----------|---------|-----------|-------------|
| 0    | (same)    | (ref)   | 240° Blue | Circle      |
| +1   | CW        | G1      | 90.6°     | Starburst   |
| -1   | CCW       | G11     | 36.5°     | Starburst   |
| +2   | CW        | G2      | 301.2°    | Hexagon     |
| -2   | CCW       | G10     | 185.9°    | Hexagon     |
| +3   | CW        | G3      | 151.8°    | Square      |
| -3   | CCW       | G9      | 335.3°    | Square      |
| +4   | CW        | G4      | 2.4°      | Triangle    |
| -4   | CCW       | G8      | 124.7°    | Triangle    |
| +5   | CW        | G5      | 212.9°    | 12-gon      |
| -5   | CCW       | G7      | 274.1°    | 12-gon      |
| 6    | (both)    | G6      | 63.5°     | Midpoint    |

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/synestesia/engine/core.py` | `draw_view_tabs()` → support 3 tabs; new `draw_keyboard_relation()` function; new keyboard-drawing helpers |
| `src/synestesia/engine/__init__.py` | Export `draw_keyboard_relation` |
| `src/synestesia/midi_visualizer/app.py` | New state (`keyboard_ref`); 3-tab logic; MIDI→ref tracking; route rendering |

No new files needed.

---

## Key Design Decisions

1. **Reference becomes the most-recently-pressed note** — each new note-on replaces the reference, consistent with the user's description. All key labels recalculate immediately.

2. **Keyboard shows 2 octaves (MIDI 48–71)** — centered on G0 (MIDI 60). This gives enough context to see all 12 relation types at once.

3. **Shape visualizer reuses existing polygon code** — the `draw_flow_relations()` function already draws inscribed n-gons with LFI gradients, sub-shapes, and directional arrows. We extract/parameterize this logic to fit the top panel.

4. **Key labels are compact** — white keys show G-label + step/direction text. Black keys show abbreviated info. Background tint is the dominant visual cue.

5. **Octave-agnostic relations** — relation is computed on G-class only (mod 12), so both octaves show the same relation for the same G-class.

6. **No new keyboard shortcuts needed** — the existing `V` key switches between tabs (adapted to cycle through 3). Keyboard tab has no sub-tabs.

---

## Open Questions for Approval

- Should the reference persist after key release, or clear when all keys are released? (Proposal: persist — the last pressed note remains the reference until a new one is pressed)
ANSWER: persist
- For the keyboard keys, should the shape be drawn as a miniature icon, or is text label + color tint sufficient? (Proposal: color tint + compact text label; the full shape lives in the top visualizer)
ANSWER: we need to draw mini shape icons colored correctly inside the keys
