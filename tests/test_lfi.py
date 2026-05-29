"""
Tests for the LFI (Liminal Flow Intonation) color system.

Run with: python -m pytest tests/ -v
(No pygame display required — these are pure-math tests.)
"""

import sys
import os
import math

# Allow running without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Patch pygame before importing engine so no display is needed
import types
pygame_stub = types.ModuleType("pygame")
pygame_stub.mixer = types.ModuleType("pygame.mixer")
pygame_stub.mixer.Sound = None
sys.modules.setdefault("pygame", pygame_stub)
sys.modules.setdefault("pygame.mixer", pygame_stub.mixer)

import numpy  # noqa: E402 — must come after stub
from synestesia.engine.core import (
    v_hue, _hsl, note_color, liminal_color, lerp_c,
    midi_to_freq, name, black,
    LFI_DATA, SEM, F_BASE, TOTAL_OCTAVES,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _hue_of(ratio):
    """Compute hue directly from a frequency ratio reduced to [1, 2)."""
    while ratio >= 2.0:
        ratio /= 2.0
    while ratio < 1.0:
        ratio *= 2.0
    v = math.log2(ratio)
    return (240.0 + 360.0 * v) % 360.0


# ── LFI_DATA integrity ────────────────────────────────────────────────────────

def test_lfi_data_has_12_entries():
    assert len(LFI_DATA) == 12

def test_lfi_data_semitone_indices_are_unique():
    indices = [entry[0] for entry in LFI_DATA]
    assert sorted(indices) == list(range(12))

def test_lfi_data_v_values_in_range():
    for entry in LFI_DATA:
        v = entry[3]
        assert 0.0 <= v < 1.0, f"v={v} out of [0,1) for {entry[1]}"

def test_lfi_data_linear_sequence_order():
    """The LFI_DATA is ordered by the Linear sequence (G+^n steps from G0)."""
    # G+ step in v-space: log2(3/2) ≈ 0.58496
    # Each entry's v should be approximately the previous + log2(3/2) mod 1
    step = math.log2(3 / 2)
    v_prev = 0.0  # G0
    for i, entry in enumerate(LFI_DATA):
        expected = (v_prev + step) % 1.0 if i > 0 else 0.0
        actual = entry[3]
        assert abs(actual - expected) < 1e-4, (
            f"Entry {i} ({entry[1]}): expected v≈{expected:.6f}, got {actual:.6f}"
        )
        v_prev = actual


# ── v_hue ─────────────────────────────────────────────────────────────────────

def test_v_hue_g0_is_blue():
    """G0 (v=0) maps to hue 240° (pure Blue)."""
    assert abs(v_hue(0.0) - 240.0) < 1e-9

def test_v_hue_output_in_range():
    for entry in LFI_DATA:
        h = v_hue(entry[3])
        assert 0.0 <= h < 360.0, f"hue={h} out of range for {entry[1]}"

def test_v_hue_anchor_table():
    """Spot-check the anchor table from the AGENTS spec."""
    expected = {
        0:  240.00,   # G0  — Blue
        1:   90.59,   # G7  — Chartreuse (G+^1)
        5:  212.93,   # G5  — Azure     (G+^5)
        6:   63.52,   # G6  — Yellow    (G+^6 / structural midpoint)
        10: 185.87,   # G10 — Cyan      (G+^10)
    }
    for i, hue_deg in expected.items():
        v = LFI_DATA[i][3]
        got = v_hue(v)
        assert abs(got - hue_deg) < 0.1, (
            f"LFI_DATA[{i}] ({LFI_DATA[i][1]}): expected hue {hue_deg}°, got {got:.2f}°"
        )


# ── _hsl → RGB ────────────────────────────────────────────────────────────────

def test_hsl_pure_blue():
    r, g, b = _hsl(240.0, 100.0, 50.0)
    assert (r, g, b) == (0, 0, 255)

def test_hsl_pure_red():
    r, g, b = _hsl(0.0, 100.0, 50.0)
    assert (r, g, b) == (255, 0, 0)

def test_hsl_white():
    r, g, b = _hsl(0.0, 0.0, 100.0)
    assert (r, g, b) == (255, 255, 255)

def test_hsl_black():
    r, g, b = _hsl(0.0, 0.0, 0.0)
    assert (r, g, b) == (0, 0, 0)

def test_hsl_output_in_byte_range():
    for entry in LFI_DATA:
        r, g, b = _hsl(v_hue(entry[3]), 100.0, 50.0)
        assert 0 <= r <= 255
        assert 0 <= g <= 255
        assert 0 <= b <= 255


# ── note_color ────────────────────────────────────────────────────────────────

def test_note_color_returns_tuple_of_3():
    col = note_color(60)
    assert len(col) == 3

def test_note_color_all_in_range():
    for midi in range(21, 109):
        r, g, b = note_color(midi)
        assert 0 <= r <= 255
        assert 0 <= g <= 255
        assert 0 <= b <= 255

def test_note_color_same_note_class_different_octaves_differ_in_lightness():
    """Higher-octave notes should be lighter (higher L in HSL)."""
    # G0 note class across octaves: midi 24 (oct 1), 36 (oct 2), 48 (oct 3), 60 (oct 4)
    cols = [note_color(m) for m in (24, 36, 48, 60)]
    # At minimum, brightness should increase — compare sum of RGB components
    brightness = [sum(c) for c in cols]
    assert brightness == sorted(brightness), "Higher octaves should be brighter"


# ── lerp_c ────────────────────────────────────────────────────────────────────

def test_lerp_c_at_zero():
    assert lerp_c((0, 0, 0), (255, 255, 255), 0.0) == (0, 0, 0)

def test_lerp_c_at_one():
    assert lerp_c((0, 0, 0), (255, 255, 255), 1.0) == (255, 255, 255)

def test_lerp_c_midpoint():
    r, g, b = lerp_c((0, 0, 0), (200, 100, 50), 0.5)
    assert r == 100
    assert g == 50
    assert b == 25

def test_lerp_c_clamps_t():
    assert lerp_c((0, 0, 0), (255, 0, 0), -1.0) == (0, 0, 0)
    assert lerp_c((0, 0, 0), (255, 0, 0), 2.0) == (255, 0, 0)


# ── midi helpers ──────────────────────────────────────────────────────────────

def test_midi_to_freq_a4():
    """MIDI 69 = A4 = 440 Hz."""
    assert abs(midi_to_freq(69) - 440.0) < 1e-9

def test_midi_to_freq_octave_doubles():
    f1 = midi_to_freq(60)
    f2 = midi_to_freq(72)
    assert abs(f2 / f1 - 2.0) < 1e-9

def test_name_format():
    """name() should return a string like 'G43' or 'G70'."""
    n = name(60)
    assert n.startswith("G")
    assert any(c.isdigit() for c in n[1:])

def test_black_keys():
    """MIDI note classes 1, 3, 6, 8, 10 are structurally distinct (accidentals)."""
    assert black(61) is True   # note class 1
    assert black(60) is False  # note class 0 (G0)
    assert black(62) is False  # note class 2 (G2)


# ── Pythagorean comma (visible artifact) ──────────────────────────────────────

def test_pythagorean_comma_angular_gap():
    """After 12 G+ steps the hue gap should be ~7.04° (the Pythagorean comma)."""
    step = math.log2(3 / 2)
    v_12 = (12 * step) % 1.0
    hue_12 = v_hue(v_12)
    gap = hue_12 - 240.0  # G0 anchor is 240°
    # The gap should be 360 * log2(3^12 / 2^19) ≈ 7.04°
    expected_gap = 360.0 * math.log2(3**12 / 2**19)
    assert abs(gap - expected_gap) < 0.01, f"comma gap {gap:.4f}° ≠ {expected_gap:.4f}°"
