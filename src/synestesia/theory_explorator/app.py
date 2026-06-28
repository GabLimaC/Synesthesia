#!/usr/bin/env python3
"""
Synesthesia — Visualization Page
LFI Generative Circle, Circle/Line Visualizer, Interval View & RGB Cluster Mixer

Module 1 — Generative Circle
  Circle with G0–G11 nodes at equal angular positions (slot n = note-class Gn).
  STANDARD: canonical LFI hues (G0 anchor = 240°).
  CUSTOM:   RGB picker for G0; all notes derived via
            hue(Gn) = (hue_G0 + 360 × v(Gn)) mod 360.
  Custom colors are shared with Module 2.

Module 2 — Circle / Line Visualizer
  Modes change the ORDER of notes around the equally-spaced circle.
  GENERATIVE  G0 at slot 0, G1 at slot 1, … G11 at slot 11.
  LINEAR      G0, G7, G2, G9, G4, G11, G6, G1, G8, G3, G10, G5 (freq order).
  CUSTOM      Drag nodes to reorder; click to play.

  Spectrum line below the circle:
    - Always 2 octaves wide (the sequence repeated twice).
    - Left-to-right order matches the active sequence.
    - Color of each band = note's current color (standard or custom).
    - Smooth gradient between adjacent bands.

Module 3 — Interval Relationship View
  Large merged circle at top, six small cards below.
  Selector toggles which relationships are visible; connections fade in/out.

Controls
  Module 1   [STANDARD] [CUSTOM]            → color mode
             Re-click [CUSTOM]              → re-open RGB picker
  Module 2   [GENERATIVE] [LINEAR] [CUSTOM] → sequence mode
             Click node                     → play tone
             Drag (CUSTOM mode)             → swap slots
  Tab bar    [GENERATIVE] [CIRCLE/LINE] [INTERVALS] → switch module
  ESC / Q    → quit
"""

import math
import colorsys
import pygame
import numpy as np
import tkinter as tk
from tkinter import colorchooser
from ..engine import LFI_DATA, v_hue, _hsl

# ── window & layout ───────────────────────────────────────────────────────────
W, H    = 1280, 800
FPS     = 60
TOP_H   = 38
CTRL_H  = 34
VIEW_TAB_H = 28

BG          = (14, 15, 20)
TOP_BG      = (10, 11, 16)
COMP_BG     = (17, 19, 26)
DIVIDER_COL = (35, 40, 55)
CTRL_BG     = (20, 22, 30)
RING_COL    = (50, 56, 74)
RING_W      = 2
NODE_R      = 20
GLOW_A      = 55

# ── LFI lookup ────────────────────────────────────────────────────────────────
V_OF    = {row[0]: row[3] for row in LFI_DATA}
LINEAR_SEQ = [row[0] for row in LFI_DATA]   # linear (v-sorted): [0,7,2,9,4,11,6,1,8,3,10,5]

# Linear (v-sorted) order for interval circles
LINEAR_ORDER = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]

# ── note frequencies (G0 = 160 Hz, all notes ascend within one octave) ────────
FREQ_BASE = 160.0

def _build_note_freqs():
    # Indexed by chromatic G-class. Each note's frequency is G0 scaled by its
    # v-value within one octave [FREQ_BASE, FREQ_BASE*2): freq = FREQ_BASE * 2**v.
    # This yields the LINEAR (frequency-ascending) sequence starting at G0.
    f = [0.0] * 12
    for n in range(12):
        f[n] = FREQ_BASE * (2.0 ** V_OF[n])
    return f

NOTE_FREQS = _build_note_freqs()

# ── audio ─────────────────────────────────────────────────────────────────────
SR = 44100

def mk_freq_sound(freq, dur=0.55, vol=0.65):
    n   = int(SR * dur)
    t   = np.linspace(0, dur, n, endpoint=False)
    env = np.ones(n)
    a   = min(int(0.012 * SR), n)
    re  = min(int(0.10  * SR), n)
    env[:a]   = np.linspace(0, 1, a)
    env[-re:] = np.linspace(1, 0, re)
    w = (0.65 * np.sin(2 * np.pi * freq * t)
       + 0.22 * np.sin(4 * np.pi * freq * t)
       + 0.13 * np.sin(6 * np.pi * freq * t))
    w *= env * 0.38 * vol
    s  = np.clip(w * 32767, -32767, 32767).astype(np.int16)
    return pygame.mixer.Sound(buffer=s.tobytes())

# ── shared color state ────────────────────────────────────────────────────────
class ColorState:
    """
    Holds either the standard LFI palette or a custom one derived from a
    user-picked G0 color.  Shared between both modules so custom colors
    appear everywhere simultaneously.
    """
    def __init__(self):
        self.is_custom   = False
        self.custom_map  = {}   # note_class → (r,g,b)
        self.custom_g0   = None # (r,g,b) of picked G0

    def color(self, n):
        if self.is_custom and self.custom_map:
            return self.custom_map[n]
        return _standard_color(n)

    def set_custom(self, g0_rgb):
        self.custom_g0  = g0_rgb
        self.custom_map = _derive_colors(g0_rgb)
        self.is_custom  = True

    def set_standard(self):
        self.is_custom = False

    def hue_of(self, n):
        """
        Hue of note-class n under the current palette.
        Standard: (240 + 360 × v(n)) mod 360  — the LFI logarithmic-spiral formula.
        Custom:   same formula but with the user's G0 hue replacing 240°.
        """
        if self.is_custom and self.custom_g0:
            r, g, b = self.custom_g0
            h0 = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)[0] * 360.0
            return (h0 + 360.0 * V_OF[n]) % 360.0
        return v_hue(V_OF[n])

# ── color helpers ─────────────────────────────────────────────────────────────
def _standard_color(n):
    return _hsl(v_hue(V_OF[n]), 100.0, 50.0)

def _derive_colors(g0_rgb):
    r, g, b = g0_rgb[0] / 255.0, g0_rgb[1] / 255.0, g0_rgb[2] / 255.0
    h, _s, _v = colorsys.rgb_to_hsv(r, g, b)
    h0 = h * 360.0
    return {n: _hsl((h0 + 360.0 * V_OF[n]) % 360.0, 100.0, 50.0)
            for n in range(12)}

def _lfi_lerp(h0, h1, t):
    """
    Interpolate between two LFI hues using the shortest arc on the colour circle.
    This is the ONLY permitted way to blend LFI colours: never interpolate in RGB.
    Result: HSL(hue, 100%, 50%) — the canonical LFI presentation colour.
    """
    diff = ((h1 - h0 + 180.0) % 360.0) - 180.0   # signed shortest arc
    return _hsl((h0 + diff * t) % 360.0, 100.0, 50.0)

# ── tkinter color picker ──────────────────────────────────────────────────────
def _tk_pick_color(initial_rgb=None):
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    init_hex = ("#{:02x}{:02x}{:02x}".format(*initial_rgb)
                if initial_rgb else "#0000ff")
    result = colorchooser.askcolor(
        title="Pick G0 color — all notes derived from this",
        color=init_hex, parent=root)
    root.destroy()
    if result and result[0]:
        return tuple(int(c) for c in result[0])
    return None

# ── geometry ──────────────────────────────────────────────────────────────────
def _xy_slot(slot, cx, cy, r, n=12, start=-90.0):
    """Equal-angular position for slot index, top = slot 0."""
    a = math.radians(start + 360.0 * slot / n)
    return cx + r * math.cos(a), cy + r * math.sin(a)

# ── node drawing ──────────────────────────────────────────────────────────────
def _draw_node(surf, x, y, col, label, fonts,
               hovered=False, active=False, drag=False, glow_alpha=GLOW_A):
    ix, iy  = int(x), int(y)
    draw_r  = NODE_R + 3 if drag else NODE_R

    if active or hovered or drag:
        gs = pygame.Surface((draw_r * 4, draw_r * 4), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*col, glow_alpha),
                           (draw_r * 2, draw_r * 2), draw_r * 2)
        surf.blit(gs, (ix - draw_r * 2, iy - draw_r * 2))

    pygame.draw.circle(surf, col, (ix, iy), draw_r)
    border = (255, 220, 60) if active else (200, 215, 240)
    pygame.draw.circle(surf, border, (ix, iy), draw_r, 2 if active else 1)

    lbl = fonts['xs'].render(label, True, (0, 0, 0))
    surf.blit(lbl, (ix - lbl.get_width() // 2, iy - lbl.get_height() // 2))

# ── button widget ─────────────────────────────────────────────────────────────
class _Btn:
    __slots__ = ('rect', 'label', 'active', 'hover')
    def __init__(self, rect, label):
        self.rect   = pygame.Rect(rect)
        self.label  = label
        self.active = self.hover = False

    def draw(self, surf, font):
        bg  = (48, 62, 100) if self.active else (26, 28, 38) if self.hover else (20, 22, 30)
        brd = (110, 140, 220) if self.active else (55, 62, 82)
        fg  = (210, 228, 255) if self.active else (110, 120, 148)
        pygame.draw.rect(surf, bg,  self.rect, border_radius=4)
        pygame.draw.rect(surf, brd, self.rect, 1, border_radius=4)
        t = font.render(self.label, True, fg)
        surf.blit(t, (self.rect.centerx - t.get_width()  // 2,
                      self.rect.centery - t.get_height() // 2))

    def hit(self, pos): return self.rect.collidepoint(pos)


# ── Module 1: Generative Circle ───────────────────────────────────────────────
class GenerativeCircle:
    _MODES = ('STANDARD', 'CUSTOM')

    def __init__(self, rect, fonts, color_state):
        self.rect        = pygame.Rect(rect)
        self.fonts       = fonts
        self.cs          = color_state
        self._hovered    = None
        self._build_buttons()

    def resize(self, rect):
        self.rect = pygame.Rect(rect)
        self._build_buttons()

    def _ctrl_rect(self):
        return pygame.Rect(self.rect.x, self.rect.y, self.rect.width, CTRL_H)

    def _content_rect(self):
        return pygame.Rect(self.rect.x, self.rect.y + CTRL_H,
                           self.rect.width, self.rect.height - CTRL_H)

    def _circle_params(self):
        cr = self._content_rect()
        cx = cr.x + cr.width  // 2
        cy = cr.y + cr.height // 2
        r  = min(cr.width, cr.height) * 0.38
        return cx, cy, r

    def _build_buttons(self):
        bw, bh = 82, 22
        by     = self.rect.y + (CTRL_H - bh) // 2
        total  = len(self._MODES) * (bw + 5) - 5
        bx     = self.rect.right - total - 10
        self.buttons = []
        for i, lbl in enumerate(self._MODES):
            b = _Btn((bx + i * (bw + 5), by, bw, bh), lbl)
            b.active = (i == 0)
            self.buttons.append(b)

    def _open_picker(self):
        col = _tk_pick_color(self.cs.custom_g0)
        if col is not None:
            self.cs.set_custom(col)
            self.buttons[0].active = False
            self.buttons[1].active = True

    def draw(self, surf):
        fonts = self.fonts
        pygame.draw.rect(surf, COMP_BG, self.rect)

        # control bar
        pygame.draw.rect(surf, CTRL_BG, self._ctrl_rect())
        t = fonts['sm'].render("GENERATIVE CIRCLE", True, (140, 158, 200))
        surf.blit(t, (self.rect.x + 10,
                      self.rect.y + (CTRL_H - t.get_height()) // 2))
        cl = fonts['xs'].render("COLOR:", True, (70, 80, 100))
        surf.blit(cl, (self.buttons[0].rect.x - cl.get_width() - 6,
                       self.buttons[0].rect.centery - cl.get_height() // 2))
        for b in self.buttons:
            b.draw(surf, fonts['xs'])

        # G0 swatch + hint when custom
        if self.cs.is_custom:
            if self.cs.custom_g0:
                sw = pygame.Rect(self.buttons[-1].rect.right + 8,
                                 self.buttons[-1].rect.y, 22, 22)
                pygame.draw.rect(surf, self.cs.custom_g0, sw, border_radius=3)
                pygame.draw.rect(surf, (140, 150, 180), sw, 1, border_radius=3)
            cr = self._content_rect()
            hint = fonts['xs'].render("re-click CUSTOM to repick G0",
                                      True, (60, 75, 108))
            surf.blit(hint, (cr.x + cr.width // 2 - hint.get_width() // 2,
                             cr.bottom - hint.get_height() - 10))
        elif not self.cs.is_custom and not self.buttons[1].active:
            pass  # standard, nothing extra

        cx, cy, r = self._circle_params()
        pygame.draw.circle(surf, RING_COL, (int(cx), int(cy)), int(r), RING_W)

        for n in range(12):
            x, y = _xy_slot(n, cx, cy, r)
            _draw_node(surf, x, y, self.cs.color(n), f"G{n}", fonts,
                       hovered=(self._hovered == n))

        pygame.draw.rect(surf, DIVIDER_COL, self.rect, 1)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, b in enumerate(self.buttons):
                if b.hit(event.pos):
                    if i == 0:
                        self.cs.set_standard()
                        self.buttons[0].active = True
                        self.buttons[1].active = False
                    else:
                        self._open_picker()
                    return True
        if event.type == pygame.MOUSEMOTION:
            for b in self.buttons:
                b.hover = b.hit(event.pos)
            self._hovered = None
            cx, cy, r = self._circle_params()
            for n in range(12):
                x, y = _xy_slot(n, cx, cy, r)
                if math.hypot(event.pos[0] - x, event.pos[1] - y) <= NODE_R:
                    self._hovered = n
                    break
        return False


# ── Module 2: Circle / Line Visualizer ───────────────────────────────────────
class CircleLineVisualizer:
    _MODES = ('GENERATIVE', 'LINEAR', 'CUSTOM')

    def __init__(self, rect, fonts, color_state):
        self.rect          = pygame.Rect(rect)
        self.fonts         = fonts
        self.cs            = color_state
        self.mode          = 0
        self.sounds        = {}
        self._custom_order = list(range(12))
        self._drag_from    = None
        self._drag_over    = None
        self._hovered      = None
        self._active_note  = None
        self._active_tick  = 0
        self._build_buttons()

    def resize(self, rect):
        self.rect = pygame.Rect(rect)
        self._build_buttons()

    def _ctrl_rect(self):
        return pygame.Rect(self.rect.x, self.rect.y, self.rect.width, CTRL_H)

    def _content_rect(self):
        return pygame.Rect(self.rect.x, self.rect.y + CTRL_H,
                           self.rect.width, self.rect.height - CTRL_H)

    def _circle_rect(self):
        cr     = self._content_rect()
        line_h = max(70, int(cr.height * 0.22))
        return pygame.Rect(cr.x, cr.y, cr.width, cr.height - line_h - 16)

    def _line_rect(self):
        cr     = self._content_rect()
        line_h = max(70, int(cr.height * 0.22))
        return pygame.Rect(cr.x + 14, cr.bottom - line_h - 6,
                           cr.width - 28, line_h)

    def _circle_params(self):
        circ = self._circle_rect()
        cx   = circ.x + circ.width  // 2
        cy   = circ.y + circ.height // 2
        r    = min(circ.width, circ.height) * 0.38
        return cx, cy, r

    def _build_buttons(self):
        bw, bh = 94, 22
        by     = self.rect.y + (CTRL_H - bh) // 2
        total  = len(self._MODES) * (bw + 5) - 5
        bx     = self.rect.right - total - 10
        self.buttons = []
        for i, lbl in enumerate(self._MODES):
            b = _Btn((bx + i * (bw + 5), by, bw, bh), lbl)
            b.active = (i == self.mode)
            self.buttons.append(b)

    def _set_mode(self, i):
        self.mode = i
        if i != 2:
            self._custom_order = list(range(12))
        self._drag_from = self._drag_over = None
        for j, b in enumerate(self.buttons):
            b.active = (j == i)

    def _sequence(self):
        if self.mode == 0: return list(range(12))
        if self.mode == 1: return list(LINEAR_SEQ)
        return list(self._custom_order)

    def _ensure_sounds(self):
        if not self.sounds:
            for n in range(12):
                self.sounds[n] = mk_freq_sound(NOTE_FREQS[n])

    def _play(self, note_class):
        self._ensure_sounds()
        self.sounds[note_class].stop()
        self.sounds[note_class].play()
        self._active_note = note_class
        self._active_tick = pygame.time.get_ticks()

    def _hit_slot(self, pos):
        cx, cy, r = self._circle_params()
        for slot in range(12):
            x, y = _xy_slot(slot, cx, cy, r)
            if math.hypot(pos[0] - x, pos[1] - y) <= NODE_R + 4:
                return slot
        return None

    def _draw_circle(self, surf):
        fonts = self.fonts
        cx, cy, r = self._circle_params()
        seq   = self._sequence()
        ticks = pygame.time.get_ticks()

        pygame.draw.circle(surf, RING_COL, (int(cx), int(cy)), int(r), RING_W)

        for slot, n in enumerate(seq):
            x, y = _xy_slot(slot, cx, cy, r)
            col  = self.cs.color(n)

            is_active  = (n == self._active_note)
            is_hovered = (slot == self._hovered)
            is_drag    = (slot == self._drag_from and self.mode == 2)

            glow = GLOW_A
            if is_active:
                age   = (ticks - self._active_tick) / 700.0
                fade  = max(0.0, 1.0 - age)
                pulse = (math.sin(ticks * 0.012) + 1.0) * 0.5
                glow  = int((0.35 + 0.45 * pulse) * fade * 255)

            _draw_node(surf, x, y, col, f"G{n}", fonts,
                       hovered=is_hovered, active=is_active,
                       drag=is_drag, glow_alpha=max(0, glow))

        if self.mode == 2 and self._drag_over is not None and self._drag_from is not None:
            dx, dy = _xy_slot(self._drag_over, cx, cy, r)
            pygame.draw.circle(surf, (210, 200, 60),
                               (int(dx), int(dy)), NODE_R + 5, 2)

        circ = self._circle_rect()
        hints = {
            0: "GENERATIVE — G0 at top, G1 at 30°, G2 at 60°, …",
            1: "LINEAR — G0, G7, G2, G9, … (G+ frequency order)",
            2: "CUSTOM — drag nodes to swap  ·  click to play",
        }
        hint = fonts['xs'].render(hints[self.mode], True, (60, 78, 112))
        surf.blit(hint, (circ.x + circ.width // 2 - hint.get_width() // 2,
                         circ.bottom - hint.get_height() - 4))

        if self._active_note is not None:
            age = (ticks - self._active_tick) / 1500.0
            if age < 1.0:
                col  = self.cs.color(self._active_note)
                info = fonts['xs'].render(
                    f"G{self._active_note}  {NOTE_FREQS[self._active_note]:.2f} Hz",
                    True, col)
                surf.blit(info, (circ.x + circ.width // 2 - info.get_width() // 2,
                                 circ.y + 6))

    def _draw_line(self, surf):
        fonts = self.fonts
        lr    = self._line_rect()
        seq   = self._sequence()

        n_bands  = 24
        band_w   = lr.width / n_bands
        bar_h    = max(18, int((lr.height - 30) * 0.55))
        bar_y    = lr.y + 22

        title = fonts['xs'].render(
            "SPECTRUM LINE  (2 octaves, sequence order)", True, (62, 78, 108))
        surf.blit(title, (lr.x, lr.y + 2))

        hues_seq = [self.cs.hue_of(seq[i % 12]) for i in range(n_bands + 1)]

        for band in range(n_bands):
            h0 = hues_seq[band]
            h1 = hues_seq[band + 1]
            x0 = int(lr.x + band * band_w)
            x1 = int(lr.x + (band + 1) * band_w)
            for px in range(x0, x1):
                t   = (px - x0) / max(1, x1 - x0)
                col = _lfi_lerp(h0, h1, t)
                pygame.draw.line(surf, col, (px, bar_y), (px, bar_y + bar_h))

        pygame.draw.rect(surf, (55, 66, 88),
                         (lr.x, bar_y, lr.width, bar_h), 1)

        mid_x = lr.x + lr.width // 2
        pygame.draw.line(surf, (160, 170, 200),
                         (mid_x, bar_y - 2), (mid_x, bar_y + bar_h + 2), 1)
        oct_lbl = fonts['xs'].render("oct 2", True, (80, 95, 130))
        surf.blit(oct_lbl, (mid_x + 3, bar_y - 1))

        for band in range(n_bands):
            n   = seq[band % 12]
            col = self.cs.color(n)
            tx  = int(lr.x + (band + 0.5) * band_w)

            pygame.draw.line(surf, (200, 210, 230),
                             (tx, bar_y - 3), (tx, bar_y + bar_h + 3), 1)

            pygame.draw.circle(surf, col, (tx, bar_y - 8), 4)
            pygame.draw.circle(surf, (180, 195, 220), (tx, bar_y - 8), 4, 1)

            lbl = fonts['xs'].render(f"G{n}", True, col)
            if band % 2 == 0:
                surf.blit(lbl, (tx - lbl.get_width() // 2,
                                bar_y - 9 - lbl.get_height() - 1))
            else:
                surf.blit(lbl, (tx - lbl.get_width() // 2,
                                bar_y + bar_h + 6))

    def draw(self, surf):
        fonts = self.fonts
        pygame.draw.rect(surf, COMP_BG, self.rect)

        pygame.draw.rect(surf, CTRL_BG, self._ctrl_rect())
        t = fonts['sm'].render("CIRCLE / LINE VISUALIZER", True, (140, 158, 200))
        surf.blit(t, (self.rect.x + 10,
                      self.rect.y + (CTRL_H - t.get_height()) // 2))
        ml = fonts['xs'].render("MODE:", True, (70, 80, 100))
        surf.blit(ml, (self.buttons[0].rect.x - ml.get_width() - 6,
                       self.buttons[0].rect.centery - ml.get_height() // 2))
        for b in self.buttons:
            b.draw(surf, fonts['xs'])

        self._draw_circle(surf)
        self._draw_line(surf)
        pygame.draw.rect(surf, DIVIDER_COL, self.rect, 1)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, b in enumerate(self.buttons):
                if b.hit(event.pos):
                    self._set_mode(i); return True
            slot = self._hit_slot(event.pos)
            if slot is not None:
                n = self._sequence()[slot]
                self._play(n)
                if self.mode == 2:
                    self._drag_from = slot
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.mode == 2 and self._drag_from is not None:
                if (self._drag_over is not None
                        and self._drag_over != self._drag_from):
                    o = self._custom_order
                    o[self._drag_from], o[self._drag_over] = \
                        o[self._drag_over], o[self._drag_from]
                self._drag_from = self._drag_over = None

        if event.type == pygame.MOUSEMOTION:
            for b in self.buttons:
                b.hover = b.hit(event.pos)
            self._hovered = self._hit_slot(event.pos)
            if self.mode == 2 and self._drag_from is not None:
                self._drag_over = self._hovered

        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Module 3: Interval Relationship View
# ═══════════════════════════════════════════════════════════════════════════════

RELS = [
    {"step": 1, "name": "±1", "shape_name": "Starburst",    "polygons": 1, "same_style": "Double solid"},
    {"step": 2, "name": "±2", "shape_name": "Hexagons",     "polygons": 2, "same_style": "Dot-dashed"},
    {"step": 3, "name": "±3", "shape_name": "Squares",      "polygons": 3, "same_style": "Long dashes"},
    {"step": 4, "name": "±4", "shape_name": "Triangles",    "polygons": 4, "same_style": "Single solid"},
    {"step": 5, "name": "±5", "shape_name": "12-gon",       "polygons": 1, "same_style": "Tight dots"},
    {"step": 6, "name": "6",  "shape_name": "Midpoint",     "polygons": 6, "same_style": "Anchored"},
]

# ── Line style tuning (merged view) ──
BASE_W          = {1: 3, 2: 3, 3: 2, 4: 2, 5: 2, 6: 10}   # base pixel width per step
DASH3_SEG       = 18  # step 2 — length of each dash+dot cycle (px)
DASH3_DASH      = 20  # step 3 — dash length (px)
DASH3_GAP       = 10  # step 3 — gap length (px)
DASH5_GAP       = 5   # step 5 — dot spacing (px)
NODE_R_MERGED   = 15   # merged view node radius (px)

LFI_COLORS = [_hsl(v_hue(V_OF[n]), 100.0, 50.0) for n in LINEAR_ORDER]
LFI_LABELS = [f"G{n}" for n in LINEAR_ORDER]
LFI_HUES   = [v_hue(V_OF[n]) for n in LINEAR_ORDER]


def _build_arc_path(idx_a, idx_b):
    """Shortest clockwise arc on the circle from idx_a to idx_b.
    Returns list of slot indices, inclusive of both ends."""
    delta = (idx_b - idx_a) % 12
    if delta <= 6:
        return [(idx_a + i) % 12 for i in range(delta + 1)]
    else:
        return [(idx_a - i) % 12 for i in range(12 - delta + 1)]


def _build_arc_path_ccw(idx_a, idx_b):
    """Counter-clockwise arc on the circle from idx_a to idx_b."""
    delta = (idx_a - idx_b) % 12
    return [(idx_a - i) % 12 for i in range(delta + 1)]


def _arc_hue(t, arc_slots, hues=None):
    """Hue at chord position t (0–1) mapped through the arc path of slot indices."""
    h = hues if hues is not None else LFI_HUES
    k = len(arc_slots) - 1
    if k == 0:
        return h[arc_slots[0]]
    arc_t = max(0.0, min(float(k), t * k))
    seg_idx = min(int(arc_t), k - 1)
    local_t = arc_t - seg_idx
    h0 = h[arc_slots[seg_idx]]
    h1 = h[arc_slots[seg_idx + 1]]
    return (h0 + (((h1 - h0 + 180.0) % 360.0) - 180.0) * local_t) % 360.0


def _col_at_hue(hue, alpha=1.0):
    col = _hsl(hue, 100.0, 50.0)
    if alpha < 1.0:
        col = (int(col[0] * alpha), int(col[1] * alpha), int(col[2] * alpha))
    return col


def _chord_point(a, b, t):
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def _draw_arc_gradient_solid(surf, a, b, arc_slots, width=2, alpha=1.0, hues=None):
    dist = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(2, int(dist / 2))
    for i in range(n):
        t_mid = (i + 0.5) / n
        col = _col_at_hue(_arc_hue(t_mid, arc_slots, hues), alpha)
        x0, y0 = _chord_point(a, b, i / n)
        x1, y1 = _chord_point(a, b, (i + 1) / n)
        pygame.draw.line(surf, col, (int(x0), int(y0)), (int(x1), int(y1)), width)


def _draw_arc_gradient_dashes(surf, a, b, arc_slots, dash=10, gap=6, width=2, alpha=1.0, hues=None):
    """Long dashes (step 4)."""
    dist = math.hypot(b[0] - a[0], b[1] - a[1])
    cycle = dash + gap
    n = max(1, int(dist / cycle))
    for i in range(n):
        t0 = i * cycle / dist
        t1 = min(t0 + dash / dist, 1.0)
        if t1 <= t0:
            continue
        seg_n = max(1, int((t1 - t0) * dist / 2))
        for s in range(seg_n):
            lt = t0 + (t1 - t0) * s / seg_n
            rt = t0 + (t1 - t0) * (s + 1) / seg_n
            col = _col_at_hue(_arc_hue((lt + rt) * 0.5, arc_slots, hues), alpha)
            x0, y0 = _chord_point(a, b, lt)
            x1, y1 = _chord_point(a, b, rt)
            pygame.draw.line(surf, col, (int(x0), int(y0)), (int(x1), int(y1)), width)


def _draw_arc_gradient_dot_dashed(surf, a, b, arc_slots, seg=12, width=2, alpha=1.0, hues=None):
    """Dash-dot pattern (step 3)."""
    dist = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(1, int(dist / seg))
    for i in range(n):
        t0 = i * seg / dist
        t1 = min((i + 1) * seg / dist, 1.0)
        if i % 2 == 0:
            seg_n = max(1, int((t1 - t0) * dist / 2))
            for s in range(seg_n):
                lt = t0 + (t1 - t0) * s / seg_n
                rt = t0 + (t1 - t0) * (s + 1) / seg_n
                col = _col_at_hue(_arc_hue((lt + rt) * 0.5, arc_slots, hues), alpha)
                x0, y0 = _chord_point(a, b, lt)
                x1, y1 = _chord_point(a, b, rt)
                pygame.draw.line(surf, col, (int(x0), int(y0)), (int(x1), int(y1)), width)
        else:
            t = (t0 + t1) * 0.5
            col = _col_at_hue(_arc_hue(t, arc_slots, hues), alpha)
            x, y = _chord_point(a, b, t)
            pygame.draw.circle(surf, col, (int(x), int(y)), width)


def _draw_arc_gradient_dotted(surf, a, b, arc_slots, gap=5, width=2, alpha=1.0, hues=None):
    """Evenly spaced dots (step 5)."""
    dist = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(2, int(dist / gap))
    for i in range(n + 1):
        t = i / n
        col = _col_at_hue(_arc_hue(t, arc_slots, hues), alpha)
        x, y = _chord_point(a, b, t)
        pygame.draw.circle(surf, col, (int(x), int(y)), width)


def _draw_step6_split_line(surf, a, b, cw_arc, ccw_arc, width=4, alpha=1.0, hues=None):
    """Step 6: single thick line — top half cw arc gradient, bottom half ccw arc gradient."""
    dx = b[0] - a[0]; dy = b[1] - a[1]
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    nx = -dy / dist; ny = dx / dist
    half_w = width / 2.0
    n = max(2, int(dist / 2))

    for o in range(width):
        offset = -half_w + o + 0.5
        ox = nx * offset; oy = ny * offset
        arc = cw_arc if o < width // 2 else ccw_arc

        for i in range(n):
            t_mid = (i + 0.5) / n
            col = _col_at_hue(_arc_hue(t_mid, arc, hues), alpha)
            x0, y0 = _chord_point(a, b, i / n)
            x1, y1 = _chord_point(a, b, (i + 1) / n)
            pygame.draw.line(surf, col,
                (int(x0 + ox), int(y0 + oy)),
                (int(x1 + ox), int(y1 + oy)), 1)


def draw_gradient_relation_line(surf, a, b, step, a_idx, b_idx, width=2, alpha=1.0, hues=None):
    if step == 6:
        cw_arc = _build_arc_path(a_idx, b_idx)
        ccw_arc = _build_arc_path_ccw(a_idx, b_idx)
        _draw_step6_split_line(surf, a, b, cw_arc, ccw_arc, width + 1, alpha, hues)
        return

    arc = _build_arc_path(a_idx, b_idx)
    if step == 1:
        dx = b[0] - a[0]; dy = b[1] - a[1]
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        nx = -dy / dist * 3; ny = dx / dist * 3
        _draw_arc_gradient_solid(surf,
            (a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), arc, width, alpha, hues)
        _draw_arc_gradient_solid(surf,
            (a[0] - nx, a[1] - ny), (b[0] - nx, b[1] - ny), arc, width, alpha, hues)
    elif step == 2:
        _draw_arc_gradient_dot_dashed(surf, a, b, arc, seg=DASH3_SEG, width=width, alpha=alpha, hues=hues)
    elif step == 3:
        _draw_arc_gradient_dashes(surf, a, b, arc, dash=DASH3_DASH, gap=DASH3_GAP, width=width, alpha=alpha, hues=hues)
    elif step == 4:
        _draw_arc_gradient_solid(surf, a, b, arc, width, alpha, hues)
    elif step == 5:
        _draw_arc_gradient_dotted(surf, a, b, arc, gap=DASH5_GAP, width=width, alpha=alpha, hues=hues)


def _seg_points(p1, p2, n):
    return [(p1[0] + (p2[0] - p1[0]) * i / n,
             p1[1] + (p2[1] - p1[1]) * i / n) for i in range(n + 1)]

def draw_double_line(surf, color, a, b, width=2, gap=3):
    dx = b[0] - a[0]; dy = b[1] - a[1]
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    nx = -dy / dist * gap; ny = dx / dist * gap
    pygame.draw.line(surf, color, (a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), width)
    pygame.draw.line(surf, color, (a[0] - nx, a[1] - ny), (b[0] - nx, b[1] - ny), width)

def draw_long_dashes(surf, color, a, b, dash=10, gap=6, width=2):
    dist = math.hypot(b[0] - a[0], b[1] - a[1])
    if dist == 0:
        return
    n = max(1, int(dist / (dash + gap)))
    pts = _seg_points(a, b, n * 2)
    for i in range(0, len(pts) - 1, 2):
        pygame.draw.line(surf, color, pts[i], pts[i + 1], width)

def draw_dot_dashed(surf, color, a, b, width=2):
    dist = math.hypot(b[0] - a[0], b[1] - a[1])
    if dist == 0:
        return
    seg = 12
    n = max(1, int(dist / seg))
    pts = _seg_points(a, b, n)
    for i in range(len(pts) - 1):
        if i % 2 == 0:
            pygame.draw.line(surf, color, pts[i], pts[i + 1], width)
        else:
            mid = ((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
            pygame.draw.circle(surf, color, (int(mid[0]), int(mid[1])), width)

def draw_dotted_line(surf, color, a, b, gap=5, width=2):
    dist = math.hypot(b[0] - a[0], b[1] - a[1])
    if dist == 0:
        return
    n = max(1, int(dist / gap))
    for i in range(n + 1):
        t = i / n
        cx = int(a[0] + (b[0] - a[0]) * t)
        cy = int(a[1] + (b[1] - a[1]) * t)
        pygame.draw.circle(surf, color, (cx, cy), width)

def draw_relation_line(surf, color, a, b, step, width=2):
    if step == 1:
        draw_double_line(surf, color, a, b, width, 3)
    elif step == 2:
        draw_dot_dashed(surf, color, a, b, width)
    elif step == 3:
        draw_long_dashes(surf, color, a, b, 20, 10, width)
    elif step == 4:
        pygame.draw.line(surf, color, a, b, width)
    elif step == 5:
        draw_dotted_line(surf, color, a, b, 4, width)
    elif step == 6:
        pygame.draw.line(surf, color, a, b, width + 1)
        pygame.draw.circle(surf, color, (int(a[0]), int(a[1])), 4)
        pygame.draw.circle(surf, color, (int(b[0]), int(b[1])), 4)


def _draw_arrow(surf, color, tip, direction, size=7):
    dx, dy = direction
    px, py = -dy, dx
    base_x = tip[0] - dx * size
    base_y = tip[1] - dy * size
    left = (base_x + px * size * 0.5, base_y + py * size * 0.5)
    right = (base_x - px * size * 0.5, base_y - py * size * 0.5)
    pygame.draw.polygon(surf, color, [tip, left, right])

def _draw_up_arrow(surf, color, center, size=8):
    tip = (center[0], center[1] - size)
    left = (center[0] - size * 0.5, center[1] + size * 0.3)
    right = (center[0] + size * 0.5, center[1] + size * 0.3)
    pygame.draw.polygon(surf, color, [tip, left, right])

def _draw_down_arrow(surf, color, center, size=8):
    tip = (center[0], center[1] + size)
    left = (center[0] - size * 0.5, center[1] - size * 0.3)
    right = (center[0] + size * 0.5, center[1] - size * 0.3)
    pygame.draw.polygon(surf, color, [tip, left, right])


def _draw_legend_sample(surf, color, y, x_start, x_end, step):
    a = (x_start, y)
    b = (x_end, y)
    draw_relation_line(surf, color, a, b, step, width=2)
    if step != 6:
        _draw_arrow(surf, color, (x_end - 2, y), (1, 0), size=6)
        _draw_arrow(surf, color, (x_start + 2, y), (-1, 0), size=6)
    else:
        pygame.draw.circle(surf, color, (int(x_start), int(y)), 4)
        pygame.draw.circle(surf, color, (int(x_end), int(y)), 4)


class IntervalView:
    _MODES = ('LINEAR', 'GENERATIVE')

    def __init__(self, rect, fonts, color_state):
        self.rect = pygame.Rect(rect)
        self.fonts = fonts
        self.cs = color_state
        self.mode = 0  # 0=LINEAR, 1=GENERATIVE
        self.merge_pct = 0.42  # fraction of height for merged view
        self.selected = {1, 2, 3, 4, 5, 6}
        self._alphas = {r['step']: 1.0 for r in RELS}
        self._sel_buttons = []
        self._mode_buttons = []
        self._build_selector()
        self._build_mode_buttons()

    def resize(self, rect):
        self.rect = pygame.Rect(rect)
        self._build_selector()
        self._build_mode_buttons()
        self._update_selector_y(self.rect.y + 8)

    def _sequence(self):
        if self.mode == 0: return list(LINEAR_SEQ)   # LINEAR
        return list(range(12))                      # GENERATIVE

    def _hues(self):
        return [self.cs.hue_of(n) for n in self._sequence()]

    def _colors(self):
        return [self.cs.color(n) for n in self._sequence()]

    def _labels(self):
        return [f"G{n}" for n in self._sequence()]

    def _geo_step(self, rel_step):
        """Effective geometric step for path tracing.
        LINEAR: step 1 ↔ 5 are inverted (star ↔ convex 12-gon).
        GENERATIVE: no inversion needed."""
        if self.mode == 0:
            if rel_step == 1: return 5
            if rel_step == 5: return 1
        return rel_step

    def _set_mode(self, i):
        self.mode = i
        for j, b in enumerate(self._mode_buttons):
            b.active = (j == i)

    def _build_mode_buttons(self):
        bw, bh = 94, 22
        bx = self.rect.right - bw * 2 - 14
        by = self.rect.y + 8
        self._mode_buttons = []
        for i, lbl in enumerate(self._MODES):
            b = _Btn((bx + i * (bw + 5), by, bw, bh), lbl)
            b.active = (i == self.mode)
            self._mode_buttons.append(b)

    def _build_selector(self):
        n = len(RELS)
        pad = 6
        mode_reserve = 210
        avail_w = self.rect.width - 20 - mode_reserve
        self._sel_bw = (avail_w - pad * (n - 1)) // n
        self._sel_bx0 = self.rect.x + 10
        self._sel_pad = pad
        self._sel_buttons = []
        for i, rel in enumerate(RELS):
            bx = self._sel_bx0 + i * (self._sel_bw + pad)
            self._sel_buttons.append(_Btn((bx, 0, self._sel_bw, 26), rel['name']))
            self._sel_buttons[-1].active = rel['step'] in self.selected

    def toggle_step(self, step):
        if step in self.selected:
            self.selected.discard(step)
        else:
            self.selected.add(step)
        for btn, rel in zip(self._sel_buttons, RELS):
            btn.active = rel['step'] in self.selected

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.merge_pct = min(0.75, self.merge_pct + 0.02)
                return True
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self.merge_pct = max(0.20, self.merge_pct - 0.02)
                return True
        if event.type == pygame.MOUSEWHEEL:
            self.merge_pct = max(0.20, min(0.75, self.merge_pct + event.y * 0.02))
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Check mode buttons
            for i, btn in enumerate(self._mode_buttons):
                if btn.hit(event.pos):
                    self._set_mode(i)
                    return True
            # Check selector buttons
            for btn in self._sel_buttons:
                if btn.hit(event.pos):
                    for rel in RELS:
                        if rel['name'] == btn.label:
                            self.toggle_step(rel['step'])
                            return True
            # Check card clicks
            for crect, step in getattr(self, '_card_rects', []):
                x, y, w, h = crect
                if x <= mx < x + w and y <= my < y + h:
                    self.toggle_step(step)
                    return True
            return False
        if event.type == pygame.MOUSEMOTION:
            for btn in self._sel_buttons:
                btn.hover = btn.hit(event.pos)
            for btn in self._mode_buttons:
                btn.hover = btn.hit(event.pos)
        return False

    def _slot_pos(self, slot, cx, cy, r):
        angle = -math.pi / 2 + 2 * math.pi * slot / 12
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    def _update_alphas(self, dt):
        speed = 4.0
        for rel in RELS:
            s = rel['step']
            target = 1.0 if s in self.selected else 0.0
            a = self._alphas[s]
            if a < target:
                a = min(target, a + speed * dt)
            elif a > target:
                a = max(target, a - speed * dt)
            self._alphas[s] = a

    def _update_selector_y(self, base_y):
        for btn in self._sel_buttons:
            btn.rect.y = base_y + 8
        for btn in self._mode_buttons:
            btn.rect.y = base_y + 34

    def _draw_selector(self, surf, base_x, base_y):
        self._update_selector_y(base_y)
        t = self.fonts['sm'].render("INTERVAL RELATIONSHIPS", True, (140, 158, 200))
        surf.blit(t, (base_x + 10, base_y + 10))
        hint = self.fonts['xs'].render("toggle to show/hide:", True, (80, 95, 120))
        surf.blit(hint, (base_x + 10, base_y + 38))
        for btn in self._sel_buttons:
            btn.draw(surf, self.fonts['xs'])
        for btn in self._mode_buttons:
            btn.draw(surf, self.fonts['xs'])

    def _draw_card(self, surf, rect, rel):
        step = rel['step']

        x, y, w, h = rect
        card_bg = (20, 22, 30)
        pygame.draw.rect(surf, card_bg, rect, border_radius=6)
        border_col = (80, 140, 220) if step in self.selected else (45, 45, 60)
        pygame.draw.rect(surf, border_col, rect, 2, border_radius=6)

        # Title
        title = self.fonts['sm'].render(f"{rel['name']}", True, (200, 200, 210))
        surf.blit(title, (x + 8, y + 4))

        margin = 4
        left_x = x + margin
        left_y = y + 22
        left_w = w // 2 - margin * 2
        left_h = h - 22 - margin

        right_x = x + w // 2 + margin
        right_y = y + 22
        right_w = w // 2 - margin * 2
        right_h = h - 22 - margin

        # ── 1. Geometric Circle View (always visible) ──
        cx = left_x + left_w // 2
        cy = left_y + left_h // 2
        r = min(left_w, left_h) // 2 - 10

        col = (120, 130, 160)
        n_poly = rel['polygons']
        geo_s = self._geo_step(step)
        for poly_i in range(n_poly):
            path = []
            cur = poly_i
            while True:
                path.append(cur)
                cur = (cur + geo_s) % 12
                if cur == poly_i:
                    break
            pts = [self._slot_pos(i, cx, cy, r) for i in path]
            for i in range(len(pts)):
                a_pt = pts[i]
                b_pt = pts[(i + 1) % len(pts)]
                draw_relation_line(surf, col, a_pt, b_pt, step, width=2)

        # Nodes — no labels
        colors = self._colors()
        for i in range(12):
            px, py = self._slot_pos(i, cx, cy, r)
            col = colors[i]
            rad = 4
            pygame.draw.circle(surf, col, (int(px), int(py)), rad)
            pygame.draw.circle(surf, (220, 220, 220), (int(px), int(py)), rad, 1)

        # ── 2. Pure Exemplar Shape (small, compact) ──
        # Place exemplar in the top-right of the right panel, small
        ecx = right_x + right_w // 2
        ecy = right_y + right_h // 2 - 18
        er = min(right_w, right_h) // 3 - 4

        star_step = 1 if self.mode == 0 else 5
        if step == 6:
            a = (ecx - er, ecy)
            b = (ecx + er, ecy)
            pygame.draw.line(surf, (160, 170, 200), (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), 2)
            pygame.draw.circle(surf, (160, 170, 200), (int(a[0]), int(a[1])), 4)
            pygame.draw.circle(surf, (160, 170, 200), (int(b[0]), int(b[1])), 4)
        elif step == star_step:
            n = 12; k = 5
            verts = []
            for i in range(n):
                angle = -math.pi / 2 + 2 * math.pi * i / n
                verts.append((ecx + er * math.cos(angle), ecy + er * math.sin(angle)))
            for i in range(n):
                a = verts[i]
                b = verts[(i + k) % n]
                pygame.draw.line(surf, (160, 170, 200), (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), 1)
        else:
            n_vertices = 12 // math.gcd(step, 12)
            poly = []
            for i in range(n_vertices):
                angle = -math.pi / 2 + 2 * math.pi * i / n_vertices
                poly.append((ecx + er * math.cos(angle), ecy + er * math.sin(angle)))
            for i in range(len(poly)):
                a = poly[i]
                b = poly[(i + 1) % len(poly)]
                pygame.draw.line(surf, (160, 170, 200), (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), 1)

        # ── 3. Texture & Vector Legend ──
        legend_y = right_y + right_h - 28
        legend_x = right_x + 4
        legend_w = right_w - 8

        st = self.fonts['xs'].render(rel['same_style'], True, (140, 140, 155))
        surf.blit(st, (legend_x, legend_y))

        line_y = legend_y + 14
        _draw_legend_sample(surf, (180, 180, 200), line_y, legend_x, legend_x + legend_w // 2, step)

        if step != 6:
            _draw_up_arrow(surf, (140, 160, 200), (legend_x + legend_w // 2 + 16, line_y), size=5)
            _draw_down_arrow(surf, (140, 160, 200), (legend_x + legend_w // 2 + 26, line_y), size=5)
        else:
            _draw_up_arrow(surf, (140, 160, 200), (legend_x + legend_w // 2 + 16, line_y), size=5)

    def _draw_merged_view(self, surf, rect):
        x, y, w, h = rect
        pygame.draw.rect(surf, (14, 16, 22), rect, border_radius=8)
        pygame.draw.rect(surf, (50, 60, 80), rect, 1, border_radius=8)

        title = self.fonts['sm'].render("MERGED VIEW", True, (160, 175, 210))
        surf.blit(title, (x + 10, y + 6))
        pct = self.fonts['xs'].render(
            f"{int(self.merge_pct * 100)}%  ↑↓/wheel", True, (80, 95, 130))
        surf.blit(pct, (x + 10 + title.get_width() + 8, y + 8))

        cx = x + w // 2
        cy = y + h // 2 + 4
        r = min(w, h) // 2 - 24

        colors = self._colors()
        hues   = self._hues()
        labels = self._labels()

        # Draw all selected paths with LFI colour gradients
        for rel in RELS:
            step = rel['step']
            alpha = self._alphas[step]
            if alpha < 0.01:
                continue
            n_poly = rel['polygons']
            geo_s = self._geo_step(step)
            for poly_i in range(n_poly):
                path = []
                cur = poly_i
                while True:
                    path.append(cur)
                    cur = (cur + geo_s) % 12
                    if cur == poly_i:
                        break
                pts = [self._slot_pos(i, cx, cy, r) for i in path]
                for i in range(len(pts)):
                    a_idx = path[i]
                    b_idx = path[(i + 1) % len(path)]
                    a_pt = pts[i]
                    b_pt = pts[(i + 1) % len(pts)]
                    base_w = BASE_W[step]
                    draw_gradient_relation_line(surf, a_pt, b_pt, step, a_idx, b_idx,
                                                 width=max(1, int(base_w * alpha)), alpha=alpha,
                                                 hues=hues)

        # Nodes with inner labels
        nr = NODE_R_MERGED
        for i in range(12):
            px, py = self._slot_pos(i, cx, cy, r)
            col = colors[i]
            ix, iy = int(px), int(py)
            pygame.draw.circle(surf, col, (ix, iy), nr)
            pygame.draw.circle(surf, (0, 0, 0), (ix, iy), nr, 1)
            lbl = self.fonts['xs'].render(labels[i], True, (0, 0, 0))
            surf.blit(lbl, (ix - lbl.get_width() // 2, iy - lbl.get_height() // 2))

    def draw(self, surf):
        pygame.draw.rect(surf, COMP_BG, self.rect)
        self._card_rects = []   # store for click detection

        pad = 8
        sel_h = 56
        merge_h = int(self.rect.height * self.merge_pct)
        cards_top = self.rect.y + merge_h + pad + sel_h
        cards_h = self.rect.height - merge_h - sel_h - pad * 3

        # Merged view at top
        merge_rect = (self.rect.x + pad, self.rect.y + pad,
                      self.rect.width - pad * 2, merge_h)
        self._draw_merged_view(surf, merge_rect)

        # Selector bar
        sel_x = self.rect.x
        sel_y = self.rect.y + merge_h + pad
        self._draw_selector(surf, sel_x, sel_y)

        # Cards grid: 3 cols × 2 rows
        cols = 3; rows = 2
        card_w = (self.rect.width - pad * (cols + 1)) // cols
        card_h = (cards_h - pad * (rows - 1)) // rows

        for idx, rel in enumerate(RELS):
            col = idx % cols
            row = idx // cols
            rx = self.rect.x + pad + col * (card_w + pad)
            ry = cards_top + pad + row * (card_h + pad)
            crect = (rx, ry, card_w, card_h)
            self._card_rects.append((crect, rel['step']))
            self._draw_card(surf, crect, rel)

        pygame.draw.rect(surf, DIVIDER_COL, self.rect, 1)

    def update(self, dt):
        self._update_alphas(dt)


# ═══════════════════════════════════════════════════════════════════════════════
# Module 4: RGB Cluster Mixer
# ═══════════════════════════════════════════════════════════════════════════════

SOURCE_NODE_R  = 14
SEL_NODE_R     = 19
PAIR_GEN_R     = 7
CLUSTER_GEN_R  = 10
LINE_W         = 3
POLYGON_ALPHA  = 30

_LINEAR_CHROM = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]  # LINEAR pos → chromatic semitone (G-class)
_LINEAR_POS_OF = {c: p for p, c in enumerate(_LINEAR_CHROM)}  # G-class → LINEAR pos

def _rgb_hex(c):
    return "#%02x%02x%02x" % c

def _copy_to_clipboard(text):
    """Copy text to the system clipboard. Tries pygame.scrap, falls back to
    tkinter. Returns True on success."""
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8"))
        return True
    except Exception:
        pass
    try:
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True
    except Exception:
        return False

def _polygon_centroid(pts):
    """Compute polygon centroid; fall back to arithmetic mean if degenerate."""
    n = len(pts)
    if n < 2:
        return pts[0]
    if n == 2:
        return ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
    a2 = 0.0; cx = 0.0; cy = 0.0
    for i in range(n):
        j = (i + 1) % n
        cross = pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
        a2 += cross
        cx += (pts[i][0] + pts[j][0]) * cross
        cy += (pts[i][1] + pts[j][1]) * cross
    if abs(a2) < 1e-9:
        return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)
    return (cx / (6 * a2 / 2), cy / (6 * a2 / 2))


def _disc_color(point, cx, cy, R, cs):
    """Positional color-disc read — the LFI combination-color method.

    A combination color is a pure function of WHERE the combined geometric
    point sits on the wheel, so any bodies sharing a centroid share a color.

    point  : (x, y) interior point (e.g. midpoint / centroid)
    cx,cy,R: wheel center + rim radius for the SAME 12 equal LINEAR slots
    cs     : ColorState (live standard/custom hues)

    Angle → interpolated LFI hue (shortest arc between bracketing rim slots),
    radius → saturation (HSL(hue, 100%·t, 50%)); rim (t=1) = full LFI color,
    center (t=0) = mid-gray. Returns an sRGB tuple.
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


def _circ_dist(p, q):
    """Circular distance between two LINEAR positions on the 12-slot circle."""
    d = abs(p - q) % 12
    return min(d, 12 - d)


class RGBClusterMixer:
    """
    RGB Cluster Mixer — color-combination layer on top of the LFI palette.
    Click nodes on the LINEAR circle to toggle selection.
    Draws pair-colour lines, polygon fill, generated-colour circles, and a live list.
    """

    def __init__(self, rect, fonts, color_state):
        self.rect     = pygame.Rect(rect)
        self.fonts    = fonts
        self.cs       = color_state
        self.selected = set()
        self._hovered = None
        self._buttons = []       # clear + step buttons
        self._build_buttons()

    def resize(self, rect):
        self.rect = pygame.Rect(rect)
        self._build_buttons()

    # ── layout ─────────────────────────────────────────────────────────────
    def _ctrl_rect(self):
        return pygame.Rect(self.rect.x, self.rect.y, self.rect.width, CTRL_H)

    def _split(self):
        """Return (circle_rect, list_rect)."""
        cr = pygame.Rect(self.rect.x, self.rect.y + CTRL_H,
                         self.rect.width, self.rect.height - CTRL_H)
        cw = int(cr.width * 0.54)
        return (pygame.Rect(cr.x, cr.y, cw, cr.height),
                pygame.Rect(cr.x + cw + 6, cr.y, cr.width - cw - 6, cr.height))

    def _circle_center_radius(self):
        circ = self._split()[0]
        c    = min(circ.width, circ.height)
        r    = int(c * 0.43)
        cx   = circ.x + circ.width // 2
        cy   = circ.y + circ.height // 2
        return cx, cy, r

    def _circle_point(self, i, cx, cy, r):
        """i = LINEAR position 0..11. Slot 0 at top."""
        a = -math.pi / 2 + 2 * math.pi * i / 12
        return cx + r * math.cos(a), cy + r * math.sin(a)

    def _palette(self):
        """Return list of 12 (r,g,b) in LINEAR position order."""
        return [self.cs.color(_LINEAR_CHROM[n]) for n in range(12)]

    # ── buttons ────────────────────────────────────────────────────────────
    def _build_buttons(self):
        ctrl_y = self.rect.y + (CTRL_H - 22) // 2
        bw, bh = 26, 22
        gap    = 4

        # Clear button
        bx = self.rect.x + 10
        self._clear_btn = _Btn((bx, ctrl_y, 58, bh), "CLEAR")

        # Step buttons
        bx = self._clear_btn.rect.right + 10
        self._step_btns = []
        for s in range(1, 7):
            b = _Btn((bx, ctrl_y, bw, bh), str(s))
            self._step_btns.append(b)
            bx += bw + gap

    def _step_button_hit(self, pos):
        for i, b in enumerate(self._step_btns):
            if b.hit(pos):
                return i + 1
        return 0

    # ── selection logic ────────────────────────────────────────────────────
    def _toggle_note(self, linear_pos):
        if linear_pos in self.selected:
            self.selected.discard(linear_pos)
        else:
            self.selected.add(linear_pos)

    def _clear_selection(self):
        self.selected.clear()

    def _step_select(self, step):
        self.selected.clear()
        i = 0
        while True:
            self.selected.add(i)
            i = (i + step) % 12
            if i == 0:
                break

    # ── generated colours ───────────────────────────────────────────────────
    def _pair_colors(self):
        cx, cy, r = self._circle_center_radius()
        sel = sorted(self.selected)
        pc = []
        for i in range(len(sel)):
            for j in range(i + 1, len(sel)):
                a, b = sel[i], sel[j]
                ax, ay = self._circle_point(a, cx, cy, r)
                bx, by = self._circle_point(b, cx, cy, r)
                mid = ((ax + bx) / 2, (ay + by) / 2)
                c = _disc_color(mid, cx, cy, r, self.cs)
                pc.append({"kind": "pair", "members": [a, b],
                           "labels": [f"G{_LINEAR_CHROM[a]}", f"G{_LINEAR_CHROM[b]}"],
                           "rgb": c, "hex": _rgb_hex(c)})
        return pc

    def _cluster_color(self):
        if not self.selected:
            return None
        cx, cy, r = self._circle_center_radius()
        sel = sorted(self.selected)
        cen = _polygon_centroid([self._circle_point(i, cx, cy, r) for i in sel])
        c = _disc_color(cen, cx, cy, r, self.cs)
        return {"kind": "cluster", "members": sel,
                "labels": [f"G{_LINEAR_CHROM[i]}" for i in sel],
                "rgb": c, "hex": _rgb_hex(c)}

    # ── drawing ────────────────────────────────────────────────────────────
    def _draw_controls(self, surf):
        fonts = self.fonts
        pygame.draw.rect(surf, CTRL_BG, self._ctrl_rect())
        t = fonts['sm'].render("RGB CLUSTER MIXER — color-combination layer", True, (140, 158, 200))
        surf.blit(t, (self.rect.x + 10, self.rect.y + (CTRL_H - t.get_height()) // 2))

        self._clear_btn.draw(surf, fonts['xs'])
        for b in self._step_btns:
            b.draw(surf, fonts['xs'])

    def _draw_circle(self, surf):
        fonts = self.fonts
        cx, cy, r = self._circle_center_radius()
        palette = self._palette()
        sel = sorted(self.selected)
        n_sel = len(sel)

        # Ring
        pygame.draw.circle(surf, RING_COL, (int(cx), int(cy)), int(r), 3)

        # Compute all circle points
        pts_label = [(i, self._circle_point(i, cx, cy, r)) for i in range(12)]

        # Polygon fill (3+ selected)
        if n_sel >= 3:
            poly_pts = [pts_label[i][1] for i in sel]
            cluster_c = _disc_color(_polygon_centroid(poly_pts), cx, cy, r, self.cs)
            poly_surf = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
            local_pts = [(x - self.rect.x, y - self.rect.y) for x, y in poly_pts]
            pygame.draw.polygon(poly_surf, (*cluster_c, POLYGON_ALPHA), local_pts)
            # outline
            for k in range(n_sel):
                a = (local_pts[k][0] - 1, local_pts[k][1] - 1)
                b = (local_pts[(k + 1) % n_sel][0] - 1, local_pts[(k + 1) % n_sel][1] - 1)
                pygame.draw.line(poly_surf, cluster_c, a, b, 1)
            surf.blit(poly_surf, (self.rect.x, self.rect.y))

        # Pair relation lines
        if n_sel >= 2:
            for i in range(n_sel):
                for j in range(i + 1, n_sel):
                    a_li, (ax, ay) = pts_label[sel[i]]
                    b_li, (bx, by) = pts_label[sel[j]]
                    pair_c = _disc_color(((ax + bx) / 2, (ay + by) / 2), cx, cy, r, self.cs)
                    pygame.draw.line(surf, pair_c, (int(ax), int(ay)), (int(bx), int(by)), LINE_W)

        # Unselected source nodes
        for li, (px, py) in pts_label:
            if li not in self.selected:
                g_class = _LINEAR_CHROM[li]
                pygame.draw.circle(surf, palette[li], (int(px), int(py)), SOURCE_NODE_R)
                pygame.draw.circle(surf, (200, 215, 240), (int(px), int(py)), SOURCE_NODE_R, 1)
                lbl = fonts['sm'].render(f"G{g_class}", True, (0, 0, 0))
                surf.blit(lbl, (int(px) - lbl.get_width() // 2,
                                int(py) - lbl.get_height() // 2))

        # Pair generated-color midpoint circles
        if n_sel >= 2:
            pair_colors = self._pair_colors()
            for pc in pair_colors:
                a_li, b_li = pc["members"]
                ax, ay = self._circle_point(a_li, cx, cy, r)
                bx, by = self._circle_point(b_li, cx, cy, r)
                mx, my = (ax + bx) / 2, (ay + by) / 2
                pygame.draw.circle(surf, pc["rgb"], (int(mx), int(my)), PAIR_GEN_R)
                pygame.draw.circle(surf, (0, 0, 0), (int(mx), int(my)), PAIR_GEN_R, 1)

        # Cluster generated-color centroid circle
        if n_sel >= 2:
            cluster = self._cluster_color()
            if cluster:
                poly_pts = [pts_label[i][1] for i in sel]
                cx_c, cy_c = _polygon_centroid(poly_pts)
                pygame.draw.circle(surf, cluster["rgb"], (int(cx_c), int(cy_c)), CLUSTER_GEN_R)
                pygame.draw.circle(surf, (255, 255, 255), (int(cx_c), int(cy_c)), CLUSTER_GEN_R, 2)

        # Selected source nodes (on top)
        for li in sel:
            px, py = pts_label[li][1]
            g_class = _LINEAR_CHROM[li]
            pygame.draw.circle(surf, palette[li], (int(px), int(py)), SEL_NODE_R)
            border = (255, 220, 60) if self._hovered == li else (200, 215, 240)
            pw = 4 if self._hovered == li else 3
            pygame.draw.circle(surf, border, (int(px), int(py)), SEL_NODE_R, pw)
            lbl = fonts['sm'].render(f"G{g_class}", True, (0, 0, 0))
            surf.blit(lbl, (int(px) - lbl.get_width() // 2,
                            int(py) - lbl.get_height() // 2))

        # Hint
        circ = self._split()[0]
        hint = fonts['xs'].render("click to toggle  ·  0-9=G0-9  -=G10  ==G11  ·  C clear", True, (60, 78, 112))
        surf.blit(hint, (circ.x + circ.width // 2 - hint.get_width() // 2,
                         circ.bottom - hint.get_height() - 4))

    def _draw_list(self, surf):
        fonts = self.fonts
        list_r = self._split()[1]
        x, y, w, h = list_r

        pygame.draw.rect(surf, (16, 18, 24), list_r, border_radius=6)
        pygame.draw.rect(surf, DIVIDER_COL, list_r, 1, border_radius=6)

        title = fonts['sm'].render("COLOR LIST", True, (140, 158, 200))
        surf.blit(title, (x + 8, y + 5))

        cx = x + 8
        cy = y + 28
        sw_sz = 22
        row_h = sw_sz + 6

        palette = self._palette()
        sel = sorted(self.selected)
        pair_colors = self._pair_colors()
        cluster = self._cluster_color()

        def _row(cy_, swatch_col, label_str, hex_str):
            pygame.draw.rect(surf, swatch_col, (cx, cy_, sw_sz, sw_sz), border_radius=3)
            pygame.draw.rect(surf, (60, 68, 85), (cx, cy_, sw_sz, sw_sz), 1, border_radius=3)
            lbl = fonts['xs'].render(label_str, True, (210, 215, 230))
            surf.blit(lbl, (cx + sw_sz + 8, cy_))
            hx = fonts['sm'].render(hex_str, True, (140, 155, 185))
            surf.blit(hx, (cx + sw_sz + 8, cy_ + sw_sz - hx.get_height() + 1))
            return cy_ + row_h

        # ── Selected source colors ──
        hdr = fonts['sm'].render("SELECTED SOURCES", True, (100, 112, 145))
        surf.blit(hdr, (cx, cy)); cy += 18
        if not sel:
            hint = fonts['xs'].render("(none)", True, (55, 60, 80))
            surf.blit(hint, (cx, cy)); cy += 18
        else:
            for li in sel:
                c = palette[li]
                g_class = _LINEAR_CHROM[li]
                cy = _row(cy, c, f"G{g_class}", _rgb_hex(c))
        cy += 6

        # ── Generated pair colors ──
        hdr2 = fonts['sm'].render("PAIR COLORS", True, (100, 112, 145))
        surf.blit(hdr2, (cx, cy)); cy += 18
        if not pair_colors:
            hint = fonts['xs'].render("(select 2+ notes)", True, (55, 60, 80))
            surf.blit(hint, (cx, cy)); cy += 18
        else:
            for pc in pair_colors:
                label_str = " + ".join(pc["labels"])
                cy = _row(cy, pc["rgb"], label_str, pc["hex"])
        cy += 6

        # ── Generated cluster color ──
        hdr3 = fonts['sm'].render("CLUSTER COLOR", True, (100, 112, 145))
        surf.blit(hdr3, (cx, cy)); cy += 18
        if not cluster:
            hint = fonts['xs'].render("(select 2+ notes)", True, (55, 60, 80))
            surf.blit(hint, (cx, cy)); cy += 18
        else:
            label_str = " + ".join(cluster["labels"])
            cy = _row(cy, cluster["rgb"], label_str, cluster["hex"])

    def draw(self, surf):
        pygame.draw.rect(surf, COMP_BG, self.rect)
        self._draw_controls(surf)
        self._draw_circle(surf)
        self._draw_list(surf)
        pygame.draw.rect(surf, DIVIDER_COL, self.rect, 1)

    # ── event handling ─────────────────────────────────────────────────────
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_c:
                self._clear_selection(); return True
            if pygame.K_0 <= event.key <= pygame.K_9:
                g = event.key - pygame.K_0
                self._toggle_note(_LINEAR_POS_OF[g]); return True
            if event.key == pygame.K_MINUS:
                self._toggle_note(_LINEAR_POS_OF[10]); return True
            if event.key == pygame.K_EQUALS:
                self._toggle_note(_LINEAR_POS_OF[11]); return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Clear button
            if self._clear_btn.hit(event.pos):
                self._clear_selection(); return True
            # Step buttons
            s = self._step_button_hit(event.pos)
            if s:
                self._step_select(s); return True
            # Circle nodes
            cx, cy, r = self._circle_center_radius()
            for li in range(12):
                px, py = self._circle_point(li, cx, cy, r)
                r_hit = SEL_NODE_R + 3 if li in self.selected else SOURCE_NODE_R + 3
                if math.hypot(event.pos[0] - px, event.pos[1] - py) <= r_hit:
                    self._toggle_note(li); return True
            return False

        if event.type == pygame.MOUSEMOTION:
            self._clear_btn.hover = self._clear_btn.hit(event.pos)
            for b in self._step_btns:
                b.hover = b.hit(event.pos)
            self._hovered = None
            cx, cy, r = self._circle_center_radius()
            for li in range(12):
                px, py = self._circle_point(li, cx, cy, r)
                r_hit = SEL_NODE_R + 3 if li in self.selected else SOURCE_NODE_R + 3
                if math.hypot(event.pos[0] - px, event.pos[1] - py) <= r_hit:
                    self._hovered = li; break

        return False

    def update(self, dt):
        pass  # no animations needed for now


# ═══════════════════════════════════════════════════════════════════════════════
# Module 5: Relation Map
# ═══════════════════════════════════════════════════════════════════════════════

RM_GEN_R       = 11   # generated-color circle radius
RM_REVEAL_W    = 6    # revealed triangle edge stroke width (colored by 1-1 pairs)
RM_TRI_ALPHA   = 210  # near-solid triangle fill when revealed
RM_SEL_W       = 3    # outline width for note-selected shapes (no fill)
RM_SLOT_QUANT  = 6    # px grid used to group overlapping generated circles


class RelationMap:
    """
    Relation Map — maps ALL pairwise (1-to-1) and triple (triangle) LFI relations
    as combination-color circles on the LINEAR circle. Geometry is hidden by
    default; clicking a generated circle plays its member notes together and
    toggles its line/triangle reveal. A view-mode selector chooses which relation
    set is shown.

    Clicking a source node toggles a note-selection highlight: every visible
    shape that includes a selected note is highlighted at once — its outline on
    the wheel and its generated circle — without occluding the other shapes (a
    separate layer from the per-slot cycle reveal). A right-side sidebar lists
    the COMBINATION color of every selected shape (big swatch, member labels,
    hex and rgb) with copyable, scrollable rows.
    """

    _MODES = ('1-to-1', 'TRIMMED TRI', 'FULL TRI', 'TRIMMED TRI + 1-to-1')

    def __init__(self, rect, fonts, color_state):
        self.rect            = pygame.Rect(rect)
        self.fonts           = fonts
        self.cs              = color_state
        self.mode            = 0
        self.sounds          = {}       # g_class → Sound (lazy)
        self._hovered        = None     # hovered slot id
        self._last_click     = None     # last clicked object (for readout)
        self._click_tick     = 0
        self._pairs          = []
        self._triangles      = []
        self._slots          = []       # grouped overlapping generated circles
        self._cycle          = {}       # slot_id → cycle index (0 = off)
        self.selected_notes  = set()    # LINEAR positions whose shapes are highlighted
        self._copy_rows      = []       # [(rect, text)] clickable sidebar rows
        self._copy_msg       = None     # transient "copied" feedback text
        self._copy_tick      = 0
        self._list_scroll    = 0        # sidebar vertical scroll offset (px)
        self._list_clip      = None     # last drawn sidebar content clip rect
        self._buttons        = []
        self._build_buttons()
        self._rebuild()

    def resize(self, rect):
        self.rect = pygame.Rect(rect)
        self._build_buttons()
        self._rebuild()

    # ── layout ─────────────────────────────────────────────────────────────
    def _ctrl_rect(self):
        return pygame.Rect(self.rect.x, self.rect.y, self.rect.width, CTRL_H)

    def _content_rect(self):
        return pygame.Rect(self.rect.x, self.rect.y + CTRL_H,
                           self.rect.width, self.rect.height - CTRL_H)

    def _split(self):
        """Return (circle_rect, list_rect)."""
        cr = self._content_rect()
        cw = int(cr.width * 0.62)
        return (pygame.Rect(cr.x, cr.y, cw, cr.height),
                pygame.Rect(cr.x + cw + 6, cr.y, cr.width - cw - 6, cr.height))

    def _circle_center_radius(self):
        circ = self._split()[0]
        c  = min(circ.width, circ.height)
        r  = int(c * 0.40)
        cx = circ.x + circ.width // 2
        cy = circ.y + circ.height // 2
        return cx, cy, r

    def _circle_point(self, i, cx, cy, r):
        """i = LINEAR position 0..11. Slot 0 at top."""
        a = -math.pi / 2 + 2 * math.pi * i / 12
        return cx + r * math.cos(a), cy + r * math.sin(a)

    def _palette(self):
        """Return list of 12 (r,g,b) in LINEAR position order."""
        return [self.cs.color(_LINEAR_CHROM[n]) for n in range(12)]

    # ── buttons ────────────────────────────────────────────────────────────
    def _build_buttons(self):
        ctrl_y = self.rect.y + (CTRL_H - 22) // 2
        bh = 22
        gap = 5

        # CLEAR button on the left
        self._clear_btn = _Btn((self.rect.x + 10, ctrl_y, 58, bh), "CLEAR")

        # Mode buttons on the right
        widths = [70, 110, 90, 170]
        total = sum(widths) + gap * (len(widths) - 1)
        bx = self.rect.right - total - 10
        self._mode_btns = []
        for i, lbl in enumerate(self._MODES):
            b = _Btn((bx, ctrl_y, widths[i], bh), lbl)
            b.active = (i == self.mode)
            self._mode_btns.append(b)
            bx += widths[i] + gap

    def _mode_button_hit(self, pos):
        for i, b in enumerate(self._mode_btns):
            if b.hit(pos):
                return i
        return None

    # ── object building ─────────────────────────────────────────────────────
    def _rebuild(self):
        """Recompute pair and triangle objects (geometry + colors)."""
        cx, cy, r = self._circle_center_radius()
        pts = [self._circle_point(i, cx, cy, r) for i in range(12)]

        self._pairs = []
        for a in range(12):
            for b in range(a + 1, 12):
                ax, ay = pts[a]; bx, by = pts[b]
                mid = ((ax + bx) / 2, (ay + by) / 2)
                col = _disc_color(mid, cx, cy, r, self.cs)
                self._pairs.append({
                    "key": ("pair", a, b),
                    "kind": "pair",
                    "members": [a, b],
                    "labels": [f"G{_LINEAR_CHROM[a]}", f"G{_LINEAR_CHROM[b]}"],
                    "rgb": col, "hex": _rgb_hex(col),
                    "point": ((ax + bx) / 2, (ay + by) / 2),
                    "geometry": ("line", (ax, ay), (bx, by)),
                })

        self._triangles = []
        for a in range(12):
            for b in range(a + 1, 12):
                for c in range(b + 1, 12):
                    tri_pts = [pts[a], pts[b], pts[c]]
                    cen = _polygon_centroid(tri_pts)
                    col = _disc_color(cen, cx, cy, r, self.cs)
                    trimmed = (_circ_dist(a, b) >= 3 and
                               _circ_dist(b, c) >= 3 and
                               _circ_dist(a, c) >= 3)
                    self._triangles.append({
                        "key": ("tri", a, b, c),
                        "kind": "triangle",
                        "members": [a, b, c],
                        "labels": [f"G{_LINEAR_CHROM[a]}", f"G{_LINEAR_CHROM[b]}",
                                   f"G{_LINEAR_CHROM[c]}"],
                        "rgb": col, "hex": _rgb_hex(col),
                        "point": cen,
                        "geometry": ("triangle", tri_pts),
                        "trimmed": trimmed,
                    })

        self._build_slots()

    def _build_slots(self):
        """Group visible objects that share (near-)identical draw points into
        slots. A slot whose members overlap is cycled through on click."""
        objs = self._visible_objects()
        groups = {}   # quantized (gx,gy) → list of objects
        order = []
        for obj in objs:
            px, py = obj["point"]
            gx = int(round(px / RM_SLOT_QUANT))
            gy = int(round(py / RM_SLOT_QUANT))
            cell = (gx, gy)
            if cell not in groups:
                groups[cell] = []
                order.append(cell)
            groups[cell].append(obj)

        self._slots = []
        for cell in order:
            members = groups[cell]
            # average point of members for a stable draw location
            mx = sum(o["point"][0] for o in members) / len(members)
            my = sum(o["point"][1] for o in members) / len(members)
            self._slots.append({
                "id": ("slot", cell[0], cell[1]),
                "point": (mx, my),
                "objects": members,
                "count": len(members),
            })
        # Drop stale cycle entries that no longer correspond to a slot.
        valid = {s["id"] for s in self._slots}
        self._cycle = {k: v for k, v in self._cycle.items() if k in valid}

    def _visible_objects(self):
        if self.mode == 0:
            return self._pairs
        if self.mode == 1:
            return [t for t in self._triangles if t["trimmed"]]
        if self.mode == 2:
            return self._triangles
        # mode 3: trimmed triangles + pairs
        return [t for t in self._triangles if t["trimmed"]] + self._pairs

    def _selected_objects(self):
        """Visible objects whose members include at least one selected note.
        With no notes selected, returns []."""
        if not self.selected_notes:
            return []
        sel = self.selected_notes
        return [o for o in self._visible_objects()
                if any(m in sel for m in o["members"])]

    def _is_selected_obj(self, obj):
        if not self.selected_notes:
            return False
        return any(m in self.selected_notes for m in obj["members"])

    def _slot_is_selected(self, slot):
        """True if any object grouped in this slot is note-selected."""
        return any(self._is_selected_obj(o) for o in slot["objects"])

    def _revealed_objects(self):
        """Objects currently revealed via clicking their generated circle
        (the per-slot cycle)."""
        out = []
        for s in self._slots:
            obj = self._revealed_obj(s)
            if obj is not None:
                out.append(obj)
        return out

    def _listed_objects(self):
        """Union of node-selected shapes and circle-revealed shapes, kept in a
        stable order and deduplicated by key. This is what the sidebar lists."""
        seen = set()
        out = []
        for o in self._selected_objects() + self._revealed_objects():
            k = o["key"]
            if k in seen:
                continue
            seen.add(k)
            out.append(o)
        return out

    def _slot_by_id(self, sid):
        for s in self._slots:
            if s["id"] == sid:
                return s
        return None

    def _revealed_obj(self, slot):
        """Return the currently-revealed object for a slot, or None (off)."""
        idx = self._cycle.get(slot["id"], 0)
        if idx <= 0:
            return None
        return slot["objects"][idx - 1]

    # ── audio ────────────────────────────────────────────────────────────────
    def _ensure_sound(self, g_class):
        if g_class not in self.sounds:
            self.sounds[g_class] = mk_freq_sound(NOTE_FREQS[g_class])
        return self.sounds[g_class]

    def _play_notes(self, linear_positions):
        for pos in linear_positions:
            g_class = _LINEAR_CHROM[pos]
            s = self._ensure_sound(g_class)
            s.stop(); s.play()

    # ── hit testing ──────────────────────────────────────────────────────────
    def _hit_slot(self, pos):
        """Nearest visible slot within hit radius, else None."""
        mx, my = pos
        best = None
        best_d = RM_GEN_R + 4
        for s in self._slots:
            px, py = s["point"]
            d = math.hypot(mx - px, my - py)
            if d <= best_d:
                best_d = d
                best = s
        return best

    def _hit_source(self, pos):
        cx, cy, r = self._circle_center_radius()
        mx, my = pos
        for i in range(12):
            px, py = self._circle_point(i, cx, cy, r)
            if math.hypot(mx - px, my - py) <= SOURCE_NODE_R + 3:
                return i
        return None

    def _pair_color(self, lin_a, lin_b):
        """1-1 relation color of two source notes: disc color at chord midpoint."""
        cx, cy, r = self._circle_center_radius()
        ax, ay = self._circle_point(lin_a, cx, cy, r)
        bx, by = self._circle_point(lin_b, cx, cy, r)
        return _disc_color(((ax + bx) / 2, (ay + by) / 2), cx, cy, r, self.cs)

    # ── drawing ────────────────────────────────────────────────────────────
    def _draw_controls(self, surf):
        fonts = self.fonts
        pygame.draw.rect(surf, CTRL_BG, self._ctrl_rect())
        t = fonts['sm'].render("RELATION MAP", True, (140, 158, 200))
        surf.blit(t, (self.rect.x + 78, self.rect.y + (CTRL_H - t.get_height()) // 2))
        self._clear_btn.draw(surf, fonts['xs'])
        for b in self._mode_btns:
            b.active = (self._mode_btns.index(b) == self.mode)
            b.draw(surf, fonts['xs'])

    def _draw_reveals(self, surf):
        """Draw revealed geometry. Pairs draw a thick line in their pair color.
        Triangles draw a near-solid fill in the triangle's actual (cluster)
        color, with thick edges colored by each edge's 1-1 pair relation."""
        tri_surf = None
        for s in self._slots:
            obj = self._revealed_obj(s)
            if obj is None:
                continue
            geom = obj["geometry"]
            if geom[0] == "line":
                (ax, ay), (bx, by) = geom[1], geom[2]
                pygame.draw.line(surf, obj["rgb"], (int(ax), int(ay)),
                                 (int(bx), int(by)), RM_REVEAL_W)
            else:  # triangle
                tri_pts = geom[1]
                if tri_surf is None:
                    tri_surf = pygame.Surface((self.rect.width, self.rect.height),
                                              pygame.SRCALPHA)
                local = [(x - self.rect.x, y - self.rect.y) for x, y in tri_pts]
                # near-solid fill = triangle's actual cluster color
                pygame.draw.polygon(tri_surf, (*obj["rgb"], RM_TRI_ALPHA), local)
                # thick edges colored by the 1-1 pair relation of the two members
                m = obj["members"]
                edges = ((0, 1), (1, 2), (2, 0))
                for ia, ib in edges:
                    ec = self._pair_color(m[ia], m[ib])
                    pygame.draw.line(tri_surf, (*ec, 255), local[ia], local[ib],
                                     RM_REVEAL_W)
        if tri_surf is not None:
            surf.blit(tri_surf, (self.rect.x, self.rect.y))

    def _draw_selection(self, surf):
        """Highlight every visible shape containing a selected note. Outline-only
        (no opaque fills) so shapes never cover each other. Each shape is drawn
        in its own combination color; its generated circle is marked separately
        in _draw_circle. Separate from the per-slot cycle reveal."""
        objs = self._selected_objects()
        if not objs:
            return
        overlay = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        ox, oy = self.rect.x, self.rect.y
        for obj in objs:
            geom = obj["geometry"]
            if geom[0] == "line":
                (ax, ay), (bx, by) = geom[1], geom[2]
                pygame.draw.line(overlay, (*obj["rgb"], 220),
                                 (ax - ox, ay - oy), (bx - ox, by - oy), RM_SEL_W)
            else:  # triangle — edges only, in the triangle's combination color
                local = [(x - ox, y - oy) for x, y in geom[1]]
                pygame.draw.polygon(overlay, (*obj["rgb"], 235), local, RM_SEL_W)
        surf.blit(overlay, (ox, oy))

    def _draw_circle(self, surf):
        fonts = self.fonts
        cx, cy, r = self._circle_center_radius()
        palette = self._palette()

        # Ring
        pygame.draw.circle(surf, RING_COL, (int(cx), int(cy)), int(r), 3)

        # Revealed geometry (under the circles)
        self._draw_reveals(surf)

        # Note-selection highlight layer (all shapes containing a selected note)
        self._draw_selection(surf)

        # Generated-color slot circles
        for s in self._slots:
            px, py = s["point"]
            hovered = (s["id"] == self._hovered)
            revealed = self._revealed_obj(s)
            sel_objs = [o for o in s["objects"] if self._is_selected_obj(o)]
            is_sel = bool(sel_objs)
            # circle color: revealed member > a selected member > first member
            if revealed is not None:
                col = revealed["rgb"]
            elif is_sel:
                col = sel_objs[0]["rgb"]
            else:
                col = s["objects"][0]["rgb"]
            cr_ = RM_GEN_R + 2 if is_sel else RM_GEN_R
            pygame.draw.circle(surf, col, (int(px), int(py)), cr_)
            if is_sel:
                # gold highlight ring marks a note-selected relation circle
                pygame.draw.circle(surf, (255, 220, 60), (int(px), int(py)),
                                   cr_ + 2, 3)
            elif revealed is not None:
                pygame.draw.circle(surf, (255, 255, 255), (int(px), int(py)),
                                   RM_GEN_R + 2, 3)
            elif hovered:
                pygame.draw.circle(surf, (255, 255, 255), (int(px), int(py)),
                                   RM_GEN_R + 2, 2)
            else:
                pygame.draw.circle(surf, (0, 0, 0), (int(px), int(py)), RM_GEN_R, 1)
            # count badge for stacked slots
            if s["count"] > 1:
                cnt = self._cycle.get(s["id"], 0)
                txt = f"{cnt}/{s['count']}" if cnt > 0 else str(s["count"])
                t = fonts['xs'].render(txt, True, (255, 255, 255))
                bw, bh = t.get_width() + 4, t.get_height()
                bx = int(px) - bw // 2
                by = int(py) - RM_GEN_R - bh - 2
                bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 170))
                surf.blit(bg, (bx, by))
                surf.blit(t, (bx + 2, by))

        # Source nodes on top
        for i in range(12):
            px, py = self._circle_point(i, cx, cy, r)
            g_class = _LINEAR_CHROM[i]
            is_sel = i in self.selected_notes
            nr = SOURCE_NODE_R + 3 if is_sel else SOURCE_NODE_R
            pygame.draw.circle(surf, palette[i], (int(px), int(py)), nr)
            border = (255, 220, 60) if is_sel else (200, 215, 240)
            pygame.draw.circle(surf, border, (int(px), int(py)), nr, 3 if is_sel else 1)
            lbl = fonts['sm'].render(f"G{g_class}", True, (0, 0, 0))
            surf.blit(lbl, (int(px) - lbl.get_width() // 2,
                            int(py) - lbl.get_height() // 2))

    def _draw_readout(self, surf):
        if self._last_click is None:
            return
        age = (pygame.time.get_ticks() - self._click_tick) / 1500.0
        if age >= 1.0:
            return
        fonts = self.fonts
        obj = self._last_click
        cr = self._content_rect()
        labels = " + ".join(obj["labels"])
        freqs = " ".join("%.1fHz" % NOTE_FREQS[_LINEAR_CHROM[p]] for p in obj["members"])
        text = f"{labels}   {obj['hex']}   {freqs}"
        alpha = int(255 * (1.0 - age))
        t = fonts['sm'].render(text, True, (210, 224, 255))
        t.set_alpha(alpha)
        x = cr.x + cr.width // 2 - t.get_width() // 2
        y = cr.y + 8
        # swatch
        sw = pygame.Surface((16, 16), pygame.SRCALPHA)
        sw.fill((*obj["rgb"], alpha))
        surf.blit(sw, (x - 24, y))
        surf.blit(t, (x, y))

    def _selected_combo_rows(self):
        """All listed shapes' COMBINATION colors as list rows, sorted stably.
        Includes both node-selected and circle-revealed shapes.
        Returns list of dicts: labels, members, rgb, hex, kind."""
        objs = self._listed_objects()
        objs = sorted(objs, key=lambda o: (len(o["members"]), tuple(o["members"])))
        rows = []
        for o in objs:
            rows.append({
                "labels": " + ".join(o["labels"]),
                "members": o["members"],
                "rgb": o["rgb"],
                "hex": o["hex"],
                "kind": o["kind"],
            })
        return rows

    def _draw_list(self, surf):
        """Right-side sidebar: the COMBINATION color of every selected shape,
        each with a big swatch, member labels, hex and rgb. Rows are clickable
        to copy and the list scrolls when it overflows."""
        fonts = self.fonts
        list_r = self._split()[1]
        x, y, w, h = list_r

        pygame.draw.rect(surf, (16, 18, 24), list_r, border_radius=6)
        pygame.draw.rect(surf, DIVIDER_COL, list_r, 1, border_radius=6)

        rows_data = self._selected_combo_rows()
        title = fonts['sm'].render(
            "COMBINATION COLORS (%d)" % len(rows_data), True, (140, 158, 200))
        surf.blit(title, (x + 10, y + 8))

        self._copy_rows = []
        pad = 10
        sw = 40                       # big swatch size
        row_h = sw + 12
        gap = 6
        inner_w = w - pad * 2

        # content area (below title, above footer) — clipped + scrollable
        head_h = 30
        foot_h = 34
        clip = pygame.Rect(x + 1, y + head_h, w - 2, h - head_h - foot_h)
        self._list_clip = clip

        if not rows_data:
            hint = fonts['xs'].render("click a node or a circle to add colors",
                                      True, (70, 78, 100))
            surf.blit(hint, (x + pad, clip.y + 6))
            self._list_scroll = 0
        else:
            total_h = len(rows_data) * (row_h + gap)
            max_scroll = max(0, total_h - clip.height)
            self._list_scroll = max(0, min(self._list_scroll, max_scroll))

            mouse = pygame.mouse.get_pos()
            prev_clip = surf.get_clip()
            surf.set_clip(clip)
            cy = clip.y - self._list_scroll
            for rd in rows_data:
                row = pygame.Rect(x + pad, cy, inner_w, row_h)
                # cull rows outside the clip
                if row.bottom >= clip.y and row.top <= clip.bottom:
                    col = rd["rgb"]
                    hexs = rd["hex"]
                    rgbs = "rgb(%d, %d, %d)" % col
                    copy_text = f"{rd['labels']}  {hexs}  {rgbs}"
                    hovering = row.collidepoint(mouse) and clip.collidepoint(mouse)
                    pygame.draw.rect(surf, (24, 27, 36) if hovering else (19, 21, 28),
                                     row, border_radius=5)
                    pygame.draw.rect(surf, (70, 90, 150) if hovering else (45, 50, 66),
                                     row, 1, border_radius=5)
                    sw_rect = pygame.Rect(row.x + 6, row.y + 6, sw, sw)
                    pygame.draw.rect(surf, col, sw_rect, border_radius=4)
                    pygame.draw.rect(surf, (60, 68, 85), sw_rect, 1, border_radius=4)
                    tx = sw_rect.right + 10
                    lbl = fonts['sm'].render(rd["labels"], True, (215, 225, 245))
                    surf.blit(lbl, (tx, row.y + 4))
                    hx = fonts['xs'].render(hexs, True, (150, 165, 195))
                    surf.blit(hx, (tx, row.y + 22))
                    rg = fonts['xs'].render(rgbs, True, (120, 132, 160))
                    surf.blit(rg, (tx, row.y + 36))
                    # only register clickable rows actually inside the clip
                    self._copy_rows.append((row.clip(clip), copy_text))
                cy += row_h + gap
            surf.set_clip(prev_clip)

            # scrollbar
            if max_scroll > 0:
                track = pygame.Rect(x + w - 6, clip.y, 4, clip.height)
                pygame.draw.rect(surf, (30, 34, 44), track, border_radius=2)
                frac = clip.height / total_h
                kh = max(20, int(clip.height * frac))
                ky = clip.y + int((clip.height - kh) * (self._list_scroll / max_scroll))
                pygame.draw.rect(surf, (80, 92, 130),
                                 (x + w - 6, ky, 4, kh), border_radius=2)

        # transient "copied" feedback
        if self._copy_msg is not None:
            age = (pygame.time.get_ticks() - self._copy_tick) / 1200.0
            if age < 1.0:
                alpha = int(255 * (1.0 - age))
                t = fonts['xs'].render(self._copy_msg, True, (180, 240, 200))
                t.set_alpha(alpha)
                surf.blit(t, (x + pad, list_r.bottom - 18))
            else:
                self._copy_msg = None

        # footer hint
        if rows_data:
            fh = fonts['xs'].render("click row = copy  ·  scroll to see all",
                                    True, (70, 78, 100))
            surf.blit(fh, (x + pad, list_r.bottom - 32))

    def draw(self, surf):
        pygame.draw.rect(surf, COMP_BG, self.rect)
        self._draw_controls(surf)
        self._draw_circle(surf)
        self._draw_list(surf)
        self._draw_readout(surf)

        # bottom hint (centered over the circle side)
        fonts = self.fonts
        circ = self._split()[0]
        hint = fonts['xs'].render(
            "click node = select shapes + tone  ·  click circle = play + cycle reveal  ·  C clear",
            True, (60, 78, 112))
        surf.blit(hint, (circ.x + circ.width // 2 - hint.get_width() // 2,
                         circ.bottom - hint.get_height() - 4))

        pygame.draw.rect(surf, DIVIDER_COL, self.rect, 1)

    # ── event handling ─────────────────────────────────────────────────────
    def _set_mode(self, mode):
        if mode != self.mode:
            self.mode = mode
            self._cycle.clear()
            self.selected_notes.clear()
            self._list_scroll = 0
            self._hovered = None
            self._build_slots()

    def _cycle_slot(self, slot):
        """Advance a slot's cycle: off → member 0 → member 1 → … → off."""
        sid = slot["id"]
        cur = self._cycle.get(sid, 0)
        nxt = (cur + 1) % (slot["count"] + 1)   # wraps to 0 (off) after last
        if nxt == 0:
            self._cycle.pop(sid, None)
            return None
        self._cycle[sid] = nxt
        return slot["objects"][nxt - 1]

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_c:
                self._cycle.clear(); self.selected_notes.clear()
                self._list_scroll = 0
                return True
            return False

        if event.type == pygame.MOUSEWHEEL:
            # scroll the sidebar list when the cursor is over it
            if self._list_clip is not None and \
               self._list_clip.collidepoint(pygame.mouse.get_pos()):
                self._list_scroll = max(0, self._list_scroll - event.y * 36)
                return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # CLEAR button
            if self._clear_btn.hit(event.pos):
                self._cycle.clear(); self.selected_notes.clear()
                self._list_scroll = 0
                return True
            # Mode buttons
            m = self._mode_button_hit(event.pos)
            if m is not None:
                self._set_mode(m); return True
            # Generated slot circle
            slot = self._hit_slot(event.pos)
            if slot is not None:
                obj = self._cycle_slot(slot)
                if obj is not None:
                    self._play_notes(obj["members"])
                    self._last_click = obj
                    self._click_tick = pygame.time.get_ticks()
                return True
            # Sidebar copy row
            for rect, text in self._copy_rows:
                if rect.collidepoint(event.pos):
                    if _copy_to_clipboard(text):
                        self._copy_msg = "copied: " + text
                        self._copy_tick = pygame.time.get_ticks()
                    return True
            # Source node: play tone + toggle note-selection highlight
            si = self._hit_source(event.pos)
            if si is not None:
                self._play_notes([si])
                if si in self.selected_notes:
                    self.selected_notes.discard(si)
                else:
                    self.selected_notes.add(si)
                self._list_scroll = 0
                g_class = _LINEAR_CHROM[si]
                col = self._palette()[si]
                self._last_click = {
                    "labels": [f"G{g_class}"], "members": [si],
                    "rgb": col, "hex": _rgb_hex(col),
                }
                self._click_tick = pygame.time.get_ticks()
                return True
            return False

        if event.type == pygame.MOUSEMOTION:
            self._clear_btn.hover = self._clear_btn.hit(event.pos)
            for b in self._mode_btns:
                b.hover = b.hit(event.pos)
            slot = self._hit_slot(event.pos)
            self._hovered = slot["id"] if slot is not None else None

        return False

    def update(self, dt):
        pass


# ── view tab bar ──────────────────────────────────────────────────────────────
def _draw_view_tab_bar(surf, fonts, w, active_tab):
    labels = ["GENERATIVE", "CIRCLE / LINE", "INTERVALS", "CLUSTER MIXER", "RELATION MAP"]
    n = len(labels)
    tab_w = w // n
    y = TOP_H
    pygame.draw.rect(surf, (10, 11, 16), (0, y, w, VIEW_TAB_H))
    pygame.draw.line(surf, DIVIDER_COL, (0, y + VIEW_TAB_H - 1), (w, y + VIEW_TAB_H - 1))

    for i, label in enumerate(labels):
        tx = i * tab_w
        is_active = (active_tab == i)
        bg = (30, 35, 55) if is_active else (14, 15, 20)
        fg = (180, 200, 255) if is_active else (70, 75, 90)
        border = (60, 80, 160) if is_active else (30, 32, 42)
        pygame.draw.rect(surf, bg, (tx, y, tab_w, VIEW_TAB_H))
        pygame.draw.rect(surf, border, (tx, y, tab_w, VIEW_TAB_H), 1)
        t = fonts['xs'].render(label, True, fg)
        surf.blit(t, (tx + tab_w // 2 - t.get_width() // 2,
                      y + VIEW_TAB_H // 2 - t.get_height() // 2))


def _hit_view_tab(mx, my, w):
    if TOP_H <= my < TOP_H + VIEW_TAB_H and 0 <= mx < w:
        return (mx * 5) // w
    return None


# ── top title bar ─────────────────────────────────────────────────────────────
def _draw_topbar(surf, fonts, w):
    pygame.draw.rect(surf, TOP_BG, (0, 0, w, TOP_H))
    pygame.draw.line(surf, DIVIDER_COL, (0, TOP_H - 1), (w, TOP_H - 1))
    title = fonts['sm'].render(
        "LIMINAL FLOW INTONATION  —  Visualization", True, (118, 142, 200))
    surf.blit(title, (w // 2 - title.get_width() // 2,
                      TOP_H // 2 - title.get_height() // 2))
    hint = fonts['xs'].render("ESC · quit", True, (42, 54, 74))
    surf.blit(hint, (w - hint.get_width() - 12,
                     TOP_H // 2 - hint.get_height() // 2))


def _make_content_rect(w, h):
    return pygame.Rect(0, TOP_H + VIEW_TAB_H, w, h - TOP_H - VIEW_TAB_H)


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    global W, H
    pygame.mixer.pre_init(SR, -16, 1, 512)
    pygame.init()

    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    pygame.display.set_caption("Synesthesia — Visualization")
    clock  = pygame.time.Clock()

    fonts = {
        'sm': pygame.font.SysFont("monospace", 15, bold=True),
        'xs': pygame.font.SysFont("monospace", 13),
    }

    cs     = ColorState()
    rect   = _make_content_rect(W, H)
    comp1  = GenerativeCircle(rect, fonts, cs)
    comp2  = CircleLineVisualizer(rect, fonts, cs)
    comp3  = IntervalView(rect, fonts, cs)
    comp4  = RGBClusterMixer(rect, fonts, cs)
    comp5  = RelationMap(rect, fonts, cs)

    active_tab = 0
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif active_tab == 2:
                    comp3.handle_event(event)
                elif active_tab == 3:
                    comp4.handle_event(event)
                elif active_tab == 4:
                    comp5.handle_event(event)
            elif event.type == pygame.MOUSEWHEEL:
                if active_tab == 2:
                    comp3.handle_event(event)
            elif event.type == pygame.VIDEORESIZE:
                W, H = event.w, event.h
                screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
                rect = _make_content_rect(W, H)
                comp1.resize(rect)
                comp2.resize(rect)
                comp3.resize(rect)
                comp4.resize(rect)
                comp5.resize(rect)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                tab = _hit_view_tab(event.pos[0], event.pos[1], W)
                if tab is not None:
                    active_tab = tab
                else:
                    if active_tab == 0:
                        comp1.handle_event(event)
                    elif active_tab == 1:
                        comp2.handle_event(event)
                    elif active_tab == 2:
                        comp3.handle_event(event)
                    elif active_tab == 3:
                        comp4.handle_event(event)
                    elif active_tab == 4:
                        comp5.handle_event(event)
            else:
                if active_tab == 0:
                    comp1.handle_event(event)
                elif active_tab == 1:
                    comp2.handle_event(event)
                elif active_tab == 2:
                    comp3.handle_event(event)
                elif active_tab == 3:
                    comp4.handle_event(event)
                elif active_tab == 4:
                    comp5.handle_event(event)

        comp3.update(dt)

        screen.fill(BG)
        if active_tab == 0:
            comp1.draw(screen)
        elif active_tab == 1:
            comp2.draw(screen)
        elif active_tab == 2:
            comp3.draw(screen)
        elif active_tab == 3:
            comp4.draw(screen)
        else:
            comp5.draw(screen)

        _draw_view_tab_bar(screen, fonts, W, active_tab)
        _draw_topbar(screen, fonts, W)
        pygame.display.flip()

    pygame.quit()
