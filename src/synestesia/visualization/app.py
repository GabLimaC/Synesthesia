#!/usr/bin/env python3
"""
Synesthesia — Visualization Page
LFI Generative Circle & Circle/Line Visualizer

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
GEN_SEQ = [row[0] for row in LFI_DATA]   # [0,7,2,9,4,11,6,1,8,3,10,5]

# Generative order for interval circles (clockwise sequence)
GENERATIVE_ORDER = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]

# ── note frequencies (G0 = 320 Hz) ───────────────────────────────────────────
FREQ_BASE = 320.0

def _build_note_freqs():
    f = [0.0] * 12
    f[0] = FREQ_BASE
    fwd  = FREQ_BASE
    for step in range(1, 7):
        fwd *= 1.5
        while fwd >= FREQ_BASE * 2: fwd /= 2
        f[step] = fwd
    bck = FREQ_BASE
    for step in range(1, 6):
        bck *= 2.0 / 3.0
        while bck < FREQ_BASE / 2: bck *= 2
        f[12 - step] = bck
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
        if self.mode == 1: return list(GEN_SEQ)
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
    {"step": 1, "name": "±1", "shape_name": "12-gon",       "polygons": 1, "same_style": "Double solid"},
    {"step": 2, "name": "±2", "shape_name": "Hexagons",     "polygons": 2, "same_style": "Single solid"},
    {"step": 3, "name": "±3", "shape_name": "Squares",      "polygons": 3, "same_style": "Dot-dashed"},
    {"step": 4, "name": "±4", "shape_name": "Triangles",    "polygons": 4, "same_style": "Long dashes"},
    {"step": 5, "name": "±5", "shape_name": "Starburst",    "polygons": 1, "same_style": "Tight dots"},
    {"step": 6, "name": "6",  "shape_name": "Midpoint",     "polygons": 6, "same_style": "Anchored"},
]

LFI_COLORS = [_hsl(v_hue(V_OF[n]), 100.0, 50.0) for n in GENERATIVE_ORDER]
LFI_LABELS = [f"G{n}" for n in GENERATIVE_ORDER]
LFI_HUES   = [v_hue(V_OF[n]) for n in GENERATIVE_ORDER]


def _draw_hue_gradient_line(surf, a, b, h1, h2, width=2, alpha=1.0):
    """Draw a straight line with hue gradient from h1 to h2 (never RGB)."""
    dist = math.hypot(b[0] - a[0], b[1] - a[1])
    steps = max(1, int(dist / 2))
    for s in range(steps):
        t0 = s / steps
        t1 = (s + 1) / steps
        sx = a[0] + (b[0] - a[0]) * t0
        sy = a[1] + (b[1] - a[1]) * t0
        ex = a[0] + (b[0] - a[0]) * t1
        ey = a[1] + (b[1] - a[1]) * t1
        col = _lfi_lerp(h1, h2, (t0 + t1) / 2)
        if alpha < 1.0:
            col = (int(col[0] * alpha), int(col[1] * alpha), int(col[2] * alpha))
        pygame.draw.line(surf, col, (int(sx), int(sy)), (int(ex), int(ey)), width)

def _draw_hue_gradient_line_offset(surf, a, b, h1, h2, width, gap, alpha=1.0):
    dx = b[0] - a[0]; dy = b[1] - a[1]
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    nx = -dy / dist * gap; ny = dx / dist * gap
    _draw_hue_gradient_line(surf, (a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), h1, h2, width, alpha)
    _draw_hue_gradient_line(surf, (a[0] - nx, a[1] - ny), (b[0] - nx, b[1] - ny), h1, h2, width, alpha)

def _draw_step6_split_line(surf, a, b, h1, h2, width=4, alpha=1.0):
    """Step 6: thick straight line split into two parallel halves.
    One half follows the shortest hue path, the other the opposite direction."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    nx = -dy / dist * (width * 0.3)
    ny = dx / dist * (width * 0.3)
    half_w = max(1, width // 2)
    n = max(2, int(dist / 2))

    # Half 1 — shortest hue path
    for i in range(n):
        t0 = i / n
        sx = a[0] + nx + (b[0] - a[0]) * t0
        sy = a[1] + ny + (b[1] - a[1]) * t0
        ex = a[0] + nx + (b[0] - a[0]) * ((i + 1) / n)
        ey = a[1] + ny + (b[1] - a[1]) * ((i + 1) / n)
        col = _lfi_lerp(h1, h2, (i + 0.5) / n)
        if alpha < 1.0:
            col = (int(col[0] * alpha), int(col[1] * alpha), int(col[2] * alpha))
        pygame.draw.line(surf, col, (int(sx), int(sy)), (int(ex), int(ey)), half_w)

    # Half 2 — opposite hue path
    diff = ((h2 - h1 + 180.0) % 360.0) - 180.0
    diff_op = diff - 360.0 if diff >= 0 else diff + 360.0
    for i in range(n):
        t0 = i / n
        sx = a[0] - nx + (b[0] - a[0]) * t0
        sy = a[1] - ny + (b[1] - a[1]) * t0
        ex = a[0] - nx + (b[0] - a[0]) * ((i + 1) / n)
        ey = a[1] - ny + (b[1] - a[1]) * ((i + 1) / n)
        col = _hsl((h1 + diff_op * (i + 0.5) / n) % 360.0, 100.0, 50.0)
        if alpha < 1.0:
            col = (int(col[0] * alpha), int(col[1] * alpha), int(col[2] * alpha))
        pygame.draw.line(surf, col, (int(sx), int(sy)), (int(ex), int(ey)), half_w)

def draw_gradient_relation_line(surf, a, b, step, h1, h2, width=2, alpha=1.0):
    if step == 6:
        _draw_step6_split_line(surf, a, b, h1, h2, width + 1, alpha)
    elif step == 1:
        _draw_hue_gradient_line_offset(surf, a, b, h1, h2, width, 3, alpha)
    else:
        _draw_hue_gradient_line(surf, a, b, h1, h2, width, alpha)


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
        pygame.draw.line(surf, color, a, b, width)
    elif step == 3:
        draw_dot_dashed(surf, color, a, b, width)
    elif step == 4:
        draw_long_dashes(surf, color, a, b, 10, 6, width)
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
    def __init__(self, rect, fonts, color_state):
        self.rect = pygame.Rect(rect)
        self.fonts = fonts
        self.cs = color_state
        self.selected = {1, 2, 3, 4, 5, 6}
        self._alphas = {r['step']: 1.0 for r in RELS}
        self._sel_buttons = []
        self._build_selector()

    def resize(self, rect):
        self.rect = pygame.Rect(rect)
        self._build_selector()
        self._update_selector_y(self.rect.y + 8)

    def _build_selector(self):
        n = len(RELS)
        pad = 6
        avail_w = self.rect.width - 20
        self._sel_bw = (avail_w - pad * (n - 1)) // n
        self._sel_bx0 = self.rect.x + 10
        self._sel_pad = pad
        self._sel_buttons = []
        for i, rel in enumerate(RELS):
            bx = self._sel_bx0 + i * (self._sel_bw + pad)
            # y will be updated in draw before rendering
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
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
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

    def _draw_selector(self, surf, base_x, base_y):
        self._update_selector_y(base_y)
        t = self.fonts['sm'].render("INTERVAL RELATIONSHIPS", True, (140, 158, 200))
        surf.blit(t, (base_x + 10, base_y + 10))
        hint = self.fonts['xs'].render("toggle to show/hide:", True, (80, 95, 120))
        surf.blit(hint, (base_x + 10, base_y + 38))
        for btn in self._sel_buttons:
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
        for poly_i in range(n_poly):
            path = []
            cur = poly_i
            while True:
                path.append(cur)
                cur = (cur + step) % 12
                if cur == poly_i:
                    break
            pts = [self._slot_pos(i, cx, cy, r) for i in path]
            for i in range(len(pts)):
                a_pt = pts[i]
                b_pt = pts[(i + 1) % len(pts)]
                draw_relation_line(surf, col, a_pt, b_pt, step, width=2)

        # Nodes — no labels
        for i in range(12):
            px, py = self._slot_pos(i, cx, cy, r)
            col = LFI_COLORS[i]
            rad = 4
            pygame.draw.circle(surf, col, (int(px), int(py)), rad)
            pygame.draw.circle(surf, (220, 220, 220), (int(px), int(py)), rad, 1)

        # ── 2. Pure Exemplar Shape (small, compact) ──
        # Place exemplar in the top-right of the right panel, small
        ecx = right_x + right_w // 2
        ecy = right_y + right_h // 2 - 18
        er = min(right_w, right_h) // 3 - 4

        if step == 6:
            a = (ecx - er, ecy)
            b = (ecx + er, ecy)
            draw_relation_line(surf, (160, 170, 200), a, b, step, 2)
        elif step == 5:
            n = 12; k = 5
            verts = []
            for i in range(n):
                angle = -math.pi / 2 + 2 * math.pi * i / n
                verts.append((ecx + er * math.cos(angle), ecy + er * math.sin(angle)))
            for i in range(n):
                a = verts[i]
                b = verts[(i + k) % n]
                draw_relation_line(surf, (160, 170, 200), a, b, step, 1)
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

        cx = x + w // 2
        cy = y + h // 2 + 4
        r = min(w, h) // 2 - 24

        # Draw all selected paths with LFI colour gradients
        for rel in RELS:
            step = rel['step']
            alpha = self._alphas[step]
            if alpha < 0.01:
                continue
            n_poly = rel['polygons']
            for poly_i in range(n_poly):
                path = []
                cur = poly_i
                while True:
                    path.append(cur)
                    cur = (cur + step) % 12
                    if cur == poly_i:
                        break
                pts = [self._slot_pos(i, cx, cy, r) for i in path]
                for i in range(len(pts)):
                    a_idx = path[i]
                    b_idx = path[(i + 1) % len(path)]
                    a_pt = pts[i]
                    b_pt = pts[(i + 1) % len(pts)]
                    h1 = LFI_HUES[a_idx]
                    h2 = LFI_HUES[b_idx]
                    draw_gradient_relation_line(surf, a_pt, b_pt, step, h1, h2,
                                                 width=max(1, int(2 * alpha)), alpha=alpha)

        # Nodes with radial labels
        for i in range(12):
            px, py = self._slot_pos(i, cx, cy, r)
            col = LFI_COLORS[i]
            pygame.draw.circle(surf, col, (int(px), int(py)), 6)
            pygame.draw.circle(surf, (220, 220, 220), (int(px), int(py)), 6, 1)
            angle = -math.pi / 2 + 2 * math.pi * i / 12
            lx = px + math.cos(angle) * 18
            ly = py + math.sin(angle) * 18
            lbl = self.fonts['xs'].render(LFI_LABELS[i], True, (200, 200, 200))
            surf.blit(lbl, (int(lx) - lbl.get_width() // 2, int(ly) - lbl.get_height() // 2))

    def draw(self, surf):
        pygame.draw.rect(surf, COMP_BG, self.rect)
        self._card_rects = []   # store for click detection

        pad = 8
        sel_h = 56
        merge_h = int(self.rect.height * 0.42)
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


# ── view tab bar ──────────────────────────────────────────────────────────────
def _draw_view_tab_bar(surf, fonts, w, active_tab):
    labels = ["GENERATIVE", "CIRCLE / LINE", "INTERVALS"]
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
        return (mx * 3) // w
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
            elif event.type == pygame.VIDEORESIZE:
                W, H = event.w, event.h
                screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
                rect = _make_content_rect(W, H)
                comp1.resize(rect)
                comp2.resize(rect)
                comp3.resize(rect)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                tab = _hit_view_tab(event.pos[0], event.pos[1], W)
                if tab is not None:
                    active_tab = tab
                else:
                    if active_tab == 0:
                        comp1.handle_event(event)
                    elif active_tab == 1:
                        comp2.handle_event(event)
                    else:
                        comp3.handle_event(event)
            else:
                if active_tab == 0:
                    comp1.handle_event(event)
                elif active_tab == 1:
                    comp2.handle_event(event)
                else:
                    comp3.handle_event(event)

        comp3.update(dt)

        screen.fill(BG)
        if active_tab == 0:
            comp1.draw(screen)
        elif active_tab == 1:
            comp2.draw(screen)
        else:
            comp3.draw(screen)

        _draw_view_tab_bar(screen, fonts, W, active_tab)
        _draw_topbar(screen, fonts, W)
        pygame.display.flip()

    pygame.quit()
