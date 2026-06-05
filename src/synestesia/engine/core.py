#!/usr/bin/env python3
"""
Liminal Flow Intonation Engine — shared core for Synesthesia project.
Contains the deterministic color system, audio synthesis, MIDI import,
and common drawing helpers used by composer.py, synesthesia.py and synestv2.py.
"""

import math
import pygame
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import mido
    MIDO_AVAILABLE = True
except ImportError:
    MIDO_AVAILABLE = False

# ── LFI color system ──────────────────────
F_BASE = 40.0
F_TOP = 10240.0
TOTAL_OCTAVES = 8.0

LFI_DATA = [
    (0, "G0", 40.0000, 0.000000),
    (7, "G7", 42.7148, 0.094738),
    (2, "G2", 45.0000, 0.169925),
    (9, "G9", 48.0542, 0.264663),
    (4, "G4", 50.6250, 0.339850),
    (11, "G11", 54.0610, 0.434588),
    (6, "G6", 56.9531, 0.509775),
    (1, "G1", 60.0000, 0.584963),
    (8, "G8", 64.0723, 0.679700),
    (3, "G3", 67.5000, 0.754888),
    (10, "G10", 72.0813, 0.849625),
    (5, "G5", 75.9375, 0.924813),
]

SEM = {LFI_DATA[i][0]: LFI_DATA[i] for i in range(12)}

# Chromatic keyboard position → LFI G-class in LINEAR (frequency) order.
# E.g., the key immediately right of G0 (chromatic semitone 1) maps to G7.
_LINEAR_CHROMATIC_MAP = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]

# ── HSL → RGB ───────────────────────────────
def _hsl(h_deg, s_pct, l_pct):
    h = (h_deg % 360) / 360.0; s = s_pct / 100.0; l = l_pct / 100.0
    if s == 0:
        v = int(l * 255)
        return v, v, v
    def f(p, q, t):
        t %= 1.0
        if t < 1/6: return p + (q - p) * 6 * t
        if t < 1/2: return q
        if t < 2/3: return p + (q - p) * (2/3 - t) * 6
        return p
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return int(f(p, q, h+1/3)*255), int(f(p, q, h)*255), int(f(p, q, h-1/3)*255)

# ── Deterministic color mapping (logarithmic spiral) ───────
def v_hue(v):
    """Map a fractional-octave position v to hue using the single LFI equation."""
    return (240.0 + 360.0 * v) % 360.0

def note_color(midi, min_l=20.0, max_l=80.0):
    s = (midi - 60) % 12
    g_class = _LINEAR_CHROMATIC_MAP[s]
    v = SEM[g_class][3]
    oh = max(0, min(TOTAL_OCTAVES, ((midi - 60) // 12) + 4))
    hue = v_hue(v)
    lt = min_l + (max_l - min_l) * (oh / TOTAL_OCTAVES)
    return _hsl(hue, 100.0, max(0, min(100, lt)))

def liminal_color(v, octave_height=4.0, saturation=100.0, min_l=20.0, max_l=80.0):
    hue = v_hue(v)
    l = min_l + (max_l - min_l) * (octave_height / TOTAL_OCTAVES)
    l = max(0.0, min(100.0, l))
    return _hsl(hue, saturation, l)

def velocity_to_saturation(velocity, sat_min=55.0, sat_max=100.0):
    t = (max(1, min(127, velocity)) - 1) / 126.0
    t = t ** 0.6
    return sat_min + (sat_max - sat_min) * t

def get_color_relative(midi_note, velocity=100, min_l=20.0, max_l=80.0):
    semitone = (midi_note - 60) % 12
    g_class = _LINEAR_CHROMATIC_MAP[semitone]  # chromatic pos → LFI class
    entry = SEM[g_class]
    v = entry[3]
    octave_height = ((midi_note - 60) // 12) + 4.0
    octave_height = max(0.0, min(TOTAL_OCTAVES, octave_height))
    sat = velocity_to_saturation(velocity)
    color = liminal_color(v, octave_height, sat, min_l, max_l)
    return color, entry[1], v, octave_height

def get_color_absolute(midi_note, velocity=100, min_l=20.0, max_l=80.0):
    freq = midi_to_freq(midi_note)
    total_height = math.log2(freq / F_BASE)
    v = total_height - math.floor(total_height)
    octave_height = max(0.0, min(TOTAL_OCTAVES, total_height))
    best = min(LFI_DATA, key=lambda e: abs(e[3] - v))
    sat = velocity_to_saturation(velocity)
    color = liminal_color(best[3], octave_height, sat, min_l, max_l)
    return color, best[1], best[3], octave_height

def get_color(midi_note, velocity=100, mode=1, min_l=20.0, max_l=80.0):
    if mode == 1:
        return get_color_relative(midi_note, velocity, min_l, max_l)
    else:
        return get_color_absolute(midi_note, velocity, min_l, max_l)

def lerp_c(a, b, t):
    t = max(0, min(1, t))
    return int(a[0]+(b[0]-a[0])*t), int(a[1]+(b[1]-a[1])*t), int(a[2]+(b[2]-a[2])*t)

def midi_to_freq(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)

def m2f(m):
    return midi_to_freq(m)

def name(m):
    sem = m % 12
    g_class = _LINEAR_CHROMATIC_MAP[sem]
    octv = m // 12 - 1
    lfi = SEM[g_class][1]
    return f"{lfi}{octv}"

def black(m):
    return m % 12 in (1, 3, 6, 8, 10)

# ── audio ─────────────────────────────────
SR = 44100

def mk_sound(midi, dur=0.3, vol=1.0):
    f = m2f(midi)
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    env = np.ones(n)
    a = min(int(.008 * SR), n); r = min(int(.04 * SR), n)
    env[:a] = np.linspace(0, 1, a)
    env[-r:] = np.linspace(1, 0, r)
    w = .75 * np.sin(2*np.pi*f*t) + .18 * np.sin(4*np.pi*f*t) + .07 * np.sin(6*np.pi*f*t)
    w *= env * .35 * vol
    s = np.clip(w * 32767, -32767, 32767).astype(np.int16)
    return pygame.mixer.Sound(buffer=s.tobytes())

# ── tkinter helper ────────────────────────
def _tk_root():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    return root

# ── data ──────────────────────────────────
class Note:
    __slots__ = ('midi', 'beat', 'color', 'hand')
    def __init__(self, m, b, hand=None):
        self.midi = m; self.beat = b; self.color = note_color(m)
        self.hand = hand

# ── MIDI import ───────────────────────────
def import_midi(comp, mi_lo=36, mi_hi=96, total_beats=128):
    if not MIDO_AVAILABLE:
        messagebox.showerror("Missing Library", "mido is not installed.\nRun: pip install mido")
        return
    root = _tk_root()
    path = filedialog.askopenfilename(
        title="Open MIDI File",
        filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")]
    )
    root.destroy()
    if not path:
        return
    try:
        mid = mido.MidiFile(path)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to read MIDI file:\n{e}")
        return

    ticks_per_beat = mid.ticks_per_beat or 480

    note_events = []
    for tk_idx, track in enumerate(mid.tracks):
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                beat = abs_tick / ticks_per_beat
                note_events.append({
                    'midi': msg.note,
                    'beat': beat,
                    'track': tk_idx,
                })

    if not note_events:
        messagebox.showwarning("Empty", "MIDI file contains no notes.")
        return

    hand_by_track = {}
    for n in note_events:
        if n['track'] not in hand_by_track:
            hand_by_track[n['track']] = 'left' if n['midi'] < 60 else 'right'

    total_tracks = len(hand_by_track)
    if total_tracks == 1:
        midi_vals = [n['midi'] for n in note_events]
        split_note = 60
        if midi_vals:
            midi_vals.sort()
            lo = midi_vals[:len(midi_vals)//2]
            hi = midi_vals[len(midi_vals)//2:]
            if lo and hi and max(lo) < min(hi):
                split_note = (max(lo) + min(hi)) // 2

    for n in note_events:
        b = n['beat']
        b = max(0, min(total_beats - 0.001, b))
        m = n['midi']
        if m < mi_lo or m > mi_hi:
            continue
        if total_tracks == 1:
            hand = 'left' if m < split_note else 'right'
        else:
            hand = 'left' if hand_by_track[n['track']] == 'left' else 'right'
        comp.notes.append(Note(m, b, hand=hand))

# ── shared constants ──────────────────────
MI_LO, MI_HI = 36, 96
N_COUNT = MI_HI - MI_LO + 1
TOTAL_BEATS = 128
DEF_BPM = 120
NR = 9
NGR = 15
KB_H = 80
TB_H = 52
BG = (22, 22, 30)
GRID_BG = (30, 32, 42)

PIANO_MIDI_MIN = 21
PIANO_MIDI_MAX = 108
PIANO_NOTE_COUNT = PIANO_MIDI_MAX - PIANO_MIDI_MIN + 1
SQUARE_ROW_H = 58
VIEW_TAB_H = 28
SUB_TAB_H = 22
NODE_RADIUS = 7
MENU_W = 240

# ── drawing helpers ─────────────────────────
def draw_rounded(surf, color, rect, r):
    pygame.draw.rect(surf, color, rect, border_radius=r)


def draw_view_tabs(surface, fonts, content_x, content_w, view_tab):
    """Draw the two-tab selector (FLOW / PIANO ROLL) at the top of the content area."""
    tab_labels = ["FLOW", "PIANO ROLL"]
    tab_w = content_w // 2
    for i, label in enumerate(tab_labels):
        tx = content_x + i * tab_w
        active = (view_tab == i)
        bg  = (30, 30, 50) if active else (14, 14, 14)
        fg  = (180, 200, 255) if active else (70, 70, 70)
        border = (60, 80, 160) if active else (35, 35, 35)
        pygame.draw.rect(surface, bg, (tx, 0, tab_w, VIEW_TAB_H))
        pygame.draw.rect(surface, border, (tx, 0, tab_w, VIEW_TAB_H), 1)
        lbl = fonts['xs'].render(label, True, fg)
        surface.blit(lbl, (tx + tab_w // 2 - lbl.get_width() // 2,
                    VIEW_TAB_H // 2 - lbl.get_height() // 2))
    hint = fonts['xs'].render("[V]", True, (40, 40, 40))
    surface.blit(hint, (content_x + content_w - hint.get_width() - 6,
                    VIEW_TAB_H // 2 - hint.get_height() // 2))


def draw_piano_roll(surface, fonts, note_states, trail_columns,
                    content_x, content_w, W, H, bg,
                    palette_pick=None, show_labels=True):
    """Draw the piano-roll view: note squares at the bottom + rising trail particles."""
    trail_area_top = VIEW_TAB_H + SUB_TAB_H
    trail_area_bot = H - SQUARE_ROW_H
    trail_area_h   = trail_area_bot - trail_area_top

    sq_w = content_w / PIANO_NOTE_COUNT
    palette_pick = palette_pick or set()

    # ── trail columns ────
    clip = pygame.Rect(content_x, trail_area_top, content_w, trail_area_h)
    old_clip = surface.get_clip()
    surface.set_clip(clip)

    for col in trail_columns:
        if col['h'] < 1:
            continue
        midi = col.get('midi_note')
        is_palette = (midi is not None and (midi - 60) % 12 in palette_pick)
        r, g, b = col['color']
        psurf = pygame.Surface((max(1, int(col['w'])), max(1, int(col['h']))), pygame.SRCALPHA)
        if is_palette:
            psurf.fill((255, 200, 60, 200))
        else:
            psurf.fill((r, g, b, 255))
        surface.blit(psurf, (int(col['x']), int(col['y'])))

    surface.set_clip(old_clip)

    # ── separator line ────
    pygame.draw.line(surface, (45, 45, 45),
                    (content_x, trail_area_bot),
                    (content_x + content_w, trail_area_bot), 1)

    # ── vertical lane grid lines ────
    for idx in range(1, PIANO_NOTE_COUNT):
        gx = content_x + idx * sq_w
        semi = (PIANO_MIDI_MIN + idx - 60) % 12
        if palette_pick and semi in palette_pick:
            pygame.draw.line(surface, (120, 100, 40), (int(gx), trail_area_top), (int(gx), H), 1)
        else:
            pygame.draw.line(surface, (60, 60, 60), (int(gx), trail_area_top), (int(gx), H), 1)

    # ── note squares ────
    ticks = pygame.time.get_ticks()
    held_semitones = set()
    for midi_note, ns in note_states.items():
        if ns.get('held'):
            held_semitones.add((midi_note - 60) % 12)
    for idx in range(PIANO_NOTE_COUNT):
        midi_note = PIANO_MIDI_MIN + idx
        sx  = content_x + idx * sq_w
        sw  = max(1.0, sq_w - 1.0)
        sy  = trail_area_bot + 3
        sh  = SQUARE_ROW_H - 6
        semi = (midi_note - 60) % 12
        is_palette = (palette_pick and semi in palette_pick)

        ns = note_states.get(midi_note)
        is_held_octave = semi in held_semitones
        if ns and ns.get('held'):
            blink      = (math.sin(ticks * 0.025) + 1) / 2
            brightness = 0.55 + 0.45 * blink
            r, g, b    = ns['color']
            color      = (int(r * brightness), int(g * brightness), int(b * brightness))
            pygame.draw.rect(surface, color,
                    (int(sx), int(sy), int(sw), int(sh)), border_radius=2)
            border = (255, 200, 60) if is_palette else (200, 200, 200)
            pygame.draw.rect(surface, border,
                    (int(sx), int(sy), int(sw), int(sh)), 1, border_radius=2)
            if show_labels:
                lbl = fonts['xs'].render(ns['label'], True, (220, 220, 220))
                bx = int(sx) + (int(sw) - lbl.get_width()) // 2
                by = int(sy) + (int(sh) - lbl.get_height()) // 2
                surface.blit(lbl, (bx, by))
        else:
            if is_palette:
                pygame.draw.rect(surface, (60, 50, 20),
                        (int(sx), int(sy), int(sw), int(sh)), border_radius=2)
                pygame.draw.rect(surface, (180, 140, 20),
                        (int(sx), int(sy), int(sw), int(sh)), 2, border_radius=2)
            else:
                pygame.draw.rect(surface, (28, 28, 28),
                        (int(sx), int(sy), int(sw), int(sh)), border_radius=2)
                pygame.draw.rect(surface, (55, 55, 55),
                        (int(sx), int(sy), int(sw), int(sh)), 1, border_radius=2)

    # ── idle hint ────
    if not note_states:
        cx   = content_x + content_w // 2
        idle = fonts['sm'].render("play a note...", True, (50, 50, 50))
        surface.blit(idle, (cx - idle.get_width() // 2,
                    trail_area_top + trail_area_h // 2 - 10))


def draw_piano_roll_sub_tabs(surface, fonts, content_x, content_w, piano_roll_sub):
    """Draw a small sub-tab bar just below the main view tabs when in Piano Roll."""
    y0 = VIEW_TAB_H
    labels = ["TILES", "NODES", "RELATIONS"]
    tw = content_w // len(labels)
    for i, label in enumerate(labels):
        tx = content_x + i * tw
        active = (piano_roll_sub == i)
        bg     = (25, 25, 40) if active else (12, 12, 12)
        fg     = (160, 180, 240) if active else (55, 55, 55)
        border = (50, 65, 130) if active else (30, 30, 30)
        pygame.draw.rect(surface, bg, (tx, y0, tw, SUB_TAB_H))
        pygame.draw.rect(surface, border, (tx, y0, tw, SUB_TAB_H), 1)
        lbl = fonts['xs'].render(label, True, fg)
        surface.blit(lbl, (tx + tw // 2 - lbl.get_width() // 2,
                    y0 + SUB_TAB_H // 2 - lbl.get_height() // 2))


# ── relations view ──────────────────────────
# LINEAR sequence (frequency order) for circle placement: G0, G7, G2, G9, G4, G11, G6, G1, G8, G3, G10, G5
_LINEAR_SEQ = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]
# G-note-class → linear-position index
_CLASS_TO_LINEAR_POS = {cls: idx for idx, cls in enumerate(_LINEAR_SEQ)}
# Linear (frequency) order lookup for bottom slots
_SLOT_TO_G_CLASS = _LINEAR_CHROMATIC_MAP  # [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]

_REL_SLOTS = 25
_REL_SLOT_LABEL_H = 14
_REL_SLOT_RECT_H = 20
_REL_SLOT_H = _REL_SLOT_LABEL_H + _REL_SLOT_RECT_H
_REL_HIGHLIGHT_GAP = 2

_TRAVEL_SPEED = 5.0
_FLOW_SPEED = 0.35
_flow_offset = 0.0
_relation_anim = {
    'prev_left': None,
    'prev_right': None,
    'last_ticks': 0,
    'travel_progress': 0.0,
    'travel_active': False,
}

_STEP_NAMES = {1: "±1 Starburst", 2: "±2 Hexagons", 3: "±3 Squares",
               4: "±4 Triangles", 5: "±5 12-gon", 6: "6 Midpoint"}
_STEP_STYLES = {1: 'double', 2: 'dotdash', 3: 'longdash',
                4: 'solid', 5: 'dotted', 6: 'anchored'}
_STEP_COLORS = {1: (0, 217, 255), 2: (255, 128, 255), 3: (255, 230, 0),
                4: (0, 230, 60), 5: (255, 150, 0), 6: (255, 50, 60)}


def _lfi_lerp(h0, h1, t):
    """Interpolate hue via shortest arc on the hue circle."""
    d = h1 - h0
    if abs(d) > 180.0:
        if d > 0: h0 += 360.0
        else: h1 += 360.0
    return (h0 + (h1 - h0) * t) % 360.0


def _arc_hue_chord(t, class_a, class_b, flow_sign=1.0, circle_seq=None):
    """Hue at chord position t (0–1) interpolated along the circle arc from class_a to class_b.
    Follows intermediate nodes on the current circle sequence.
    flow_sign: 1.0 = flow from class_b to class_a, -1.0 = flow from class_a to class_b.
    circle_seq: list of 12 G-classes in circle position order. Defaults to LINEAR (frequency) order."""
    if circle_seq is None:
        circle_seq = _LINEAR_SEQ
    class_to_pos = {cls: idx for idx, cls in enumerate(circle_seq)}
    t = (t - _flow_offset * flow_sign) % 1.0
    pa = class_to_pos[class_a]
    pb = class_to_pos[class_b]
    delta = (pb - pa) % 12
    if delta <= 6:
        arc_slots = [(pa + i) % 12 for i in range(delta + 1)]
    else:
        arc_slots = [(pa - i) % 12 for i in range(12 - delta + 1)]
    hues = []
    for slot in arc_slots:
        cls = circle_seq[slot]
        hues.append(v_hue(SEM[cls][3]))
    k = len(arc_slots) - 1
    if k == 0:
        return hues[0]
    arc_t = max(0.0, min(float(k), t * k))
    seg_idx = min(int(arc_t), k - 1)
    local_t = arc_t - seg_idx
    h0 = hues[seg_idx]; h1 = hues[seg_idx + 1]
    return _lfi_lerp(h0, h1, local_t)


def _compute_generative_step(class_a, class_b):
    """Return (step, direction) for two note classes in GENERATIVE order.
    step = 1..6, direction = 'cw'|'ccw'."""
    # Generative order: position = class number itself
    step_cw = (class_b - class_a) % 12
    step_ccw = (class_a - class_b) % 12
    if step_cw <= step_ccw:
        return step_cw, 'cw'
    else:
        return step_ccw, 'ccw'


def _draw_arrow_tip(surf, color, tip, angle, size=10):
    """Draw arrowhead at tip pointing in direction angle (radians)."""
    pts = [
        tip,
        (tip[0] - size * math.cos(angle - math.pi / 7),
         tip[1] - size * math.sin(angle - math.pi / 7)),
        (tip[0] - size * math.cos(angle + math.pi / 7),
         tip[1] - size * math.sin(angle + math.pi / 7)),
    ]
    pygame.draw.polygon(surf, color, [(int(p[0]), int(p[1])) for p in pts])


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


def _draw_style_line(surf, x0, y0, x1, y1, color, style, width, step):
    """Draw a line with the given style between two points."""
    import math as _m
    dx, dy = x1 - x0, y1 - y0
    length = _m.hypot(dx, dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux

    if style == 'double':
        offset = max(1, width)
        for sign in (-1, 1):
            ox, oy = x0 + sign * offset * nx, y0 + sign * offset * ny
            ex, ey = x1 + sign * offset * nx, y1 + sign * offset * ny
            pygame.draw.line(surf, color, (int(ox), int(oy)), (int(ex), int(ey)), max(1, width - 1))
    elif style == 'dotdash':
        seg = 8; gap = 6; dot = 3; dgap = 4
        cycle = seg + gap + dot + dgap
        pos = 0
        while pos < length:
            seg_end = min(pos + seg, length)
            sx = x0 + pos * ux; sy = y0 + pos * uy
            ex = x0 + seg_end * ux; ey = y0 + seg_end * uy
            pygame.draw.line(surf, color, (int(sx), int(sy)), (int(ex), int(ey)), width)
            pos += seg + gap
            dot_pos = min(pos + dot, length)
            if dot_pos > pos:
                dx_ = x0 + pos * ux; dy_ = y0 + pos * uy
                ex_ = x0 + dot_pos * ux; ey_ = y0 + dot_pos * uy
                pygame.draw.line(surf, color, (int(dx_), int(dy_)), (int(ex_), int(ey_)), width)
            pos += dot + dgap
    elif style == 'longdash':
        dash = 14; gap = 8
        cycle = dash + gap
        pos = 0
        while pos < length:
            end = min(pos + dash, length)
            sx = x0 + pos * ux; sy = y0 + pos * uy
            ex = x0 + end * ux; ey = y0 + end * uy
            pygame.draw.line(surf, color, (int(sx), int(sy)), (int(ex), int(ey)), max(1, width - 1))
            pos += cycle
    elif style == 'dotted':
        spacing = 5
        pos = 0
        while pos < length:
            px = x0 + pos * ux; py = y0 + pos * uy
            pygame.draw.circle(surf, color, (int(px), int(py)), max(1, width - 1))
            pos += spacing
    elif style == 'anchored':
        half_w = max(2, width // 2)
        for sign in (-1, 1):
            ox, oy = x0 + sign * half_w * nx, y0 + sign * half_w * ny
            ex, ey = x1 + sign * half_w * nx, y1 + sign * half_w * ny
            pygame.draw.line(surf, color, (int(ox), int(oy)), (int(ex), int(ey)), max(2, half_w))
    else:  # 'solid'
        pygame.draw.line(surf, color, (int(x0), int(y0)), (int(x1), int(y1)), width)


def _build_relations_slots():
    """Return list of (g_class, is_central) for each of the 25 display slots.
    Uses the LINEAR (frequency) sequence, centered on G0."""
    slots = []
    for li in range(6):
        slots.append((_SLOT_TO_G_CLASS[li], False))
    for li in [6, 7, 8, 9, 10, 11, 0, 1, 2, 3, 4, 5, 6]:
        slots.append((_SLOT_TO_G_CLASS[li], True))
    for li in [7, 8, 9, 10, 11, 0]:
        slots.append((_SLOT_TO_G_CLASS[li], False))
    return slots


def draw_piano_roll_relations(surface, fonts, note_states, relation_pair,
                              content_x, content_w, W, H, bg, chords_mode=False, circle_sequence="pitch"):
    """Relations view: circle + big box (pair visualizer) + bottom slots."""
    import math as _m
    area_top = VIEW_TAB_H + SUB_TAB_H
    highlight_h = _REL_SLOT_RECT_H
    highlight_y = H - _REL_SLOT_H - _REL_HIGHLIGHT_GAP - highlight_h
    slot_y = H - _REL_SLOT_H
    free_h = highlight_y - area_top
    margin = 12

    # ── circle sequence ──
    if circle_sequence == "linear":
        circle_seq = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]
    else:
        circle_seq = [0, 5, 10, 3, 8, 1, 6, 11, 4, 9, 2, 7]
    class_to_circle_pos = {cls: idx for idx, cls in enumerate(circle_seq)}

    # ── compute active note-class colors (only held) ──
    active_classes = {}
    for midi_note, ns in note_states.items():
        if ns.get('held'):
            semi = (midi_note - 60) % 12
            g_class = _LINEAR_CHROMATIC_MAP[semi]
            if g_class not in active_classes:
                active_classes[g_class] = ns['color']

    # ── relation animation timing ──
    global _flow_offset
    now = pygame.time.get_ticks()
    dt = (now - _relation_anim['last_ticks']) / 1000.0
    dt = min(dt, 0.05)
    _relation_anim['last_ticks'] = now

    cur_left = relation_pair['left'][0] if relation_pair and relation_pair.get('left') else None
    cur_right = relation_pair['right'][0] if relation_pair and relation_pair.get('right') else None
    if cur_left != _relation_anim['prev_left'] or cur_right != _relation_anim['prev_right']:
        if cur_left is not None and cur_right is not None and cur_left != cur_right:
            _relation_anim['travel_active'] = True
            _relation_anim['travel_progress'] = 0.0
            _flow_offset = 0.0
        _relation_anim['prev_left'] = cur_left
        _relation_anim['prev_right'] = cur_right

    if _relation_anim['travel_active']:
        _relation_anim['travel_progress'] += _TRAVEL_SPEED * dt
        if _relation_anim['travel_progress'] >= 1.0:
            _relation_anim['travel_progress'] = 0.0
            _relation_anim['travel_active'] = False

    _flow_offset = (_flow_offset + _FLOW_SPEED * dt) % 1.0

    # ── layout split: circle (left ~35%) | big box (right ~65%) ──
    circle_diam = min(free_h - 2 * margin, int(content_w * 0.35))
    circle_x = content_x + margin
    circle_y = area_top + (free_h - circle_diam) // 2
    circle_cx = circle_x + circle_diam // 2
    circle_cy = circle_y + circle_diam // 2
    circle_r = circle_diam // 2 - 26

    box_x = circle_x + circle_diam + 14
    box_w = content_x + content_w - box_x - margin
    box_h = min(free_h - 2 * margin, 260)
    box_y = area_top + (free_h - box_h) // 2

    # ═══════════════════════════════════════════
    # CIRCLE VIEW — note circle view with gradient chord
    # ═══════════════════════════════════════════
    circ_surf = pygame.Surface((circle_diam, circle_diam), pygame.SRCALPHA)
    circ_surf.fill((12, 12, 18, 220))
    pygame.draw.rect(circ_surf, (50, 50, 60), (0, 0, circle_diam, circle_diam), 1, border_radius=8)
    surface.blit(circ_surf, (circle_x, circle_y))

    seq_label = "Pitch Space" if circle_sequence != "linear" else "Linear"
    title_line = fonts['xs'].render(f"NOTE CIRCLE — {seq_label}", True, (140, 140, 150))
    surface.blit(title_line, (circle_cx - title_line.get_width() // 2, circle_y - 16))

    # 12 nodes at equal angles, ordered by the active sequence
    node_radius = min(8, max(4, circle_r // 8))
    node_positions = {}

    # collect relation pair classes (stay lit even when released)
    pair_classes = set()
    if relation_pair:
        left_entry = relation_pair.get('left')
        right_entry = relation_pair.get('right')
        if right_entry: pair_classes.add(right_entry[0])

    for idx, cls in enumerate(circle_seq):
        ang = -2 * _m.pi * idx / 12 - _m.pi / 2
        nx = circle_cx - circle_r * _m.cos(ang)
        ny = circle_cy + circle_r * _m.sin(ang)
        node_positions[cls] = (nx, ny)
        v_val = SEM[cls][3]
        hue = v_hue(v_val)
        node_color = _hsl(hue, 100, 50)

        is_held = cls in active_classes
        is_pair = cls in pair_classes

        if is_held or is_pair:
            tex_col = node_color
            if is_held:
                pygame.draw.circle(surface, (255, 255, 255), (int(nx), int(ny)), node_radius + 4, 2)
        else:
            tex_col = tuple(int(c * 0.3) for c in node_color)
        pygame.draw.circle(surface, tex_col, (int(nx), int(ny)), node_radius)
        pygame.draw.circle(surface, (200, 200, 200), (int(nx), int(ny)), node_radius, 1)
        if circle_r > 60:
            lbl = fonts['xs'].render(f"G{cls}", True, (120, 120, 120))
            lx = int(nx - lbl.get_width() // 2)
            ly = int(ny + node_radius + 4)
            surface.blit(lbl, (lx, ly))

    # ── polygon shadow + chord for relation pair ──
    if chords_mode:
        held_classes = sorted(active_classes.keys())
        n_held = len(held_classes)
        if n_held >= 2:
            # ── 1. polygon shadows (deduplicated by step) ──
            drawn_step_shadows = set()
            for i in range(n_held):
                for j in range(i + 1, n_held):
                    step, _ = _compute_generative_step(held_classes[i], held_classes[j])
                    if step in drawn_step_shadows:
                        continue
                    drawn_step_shadows.add(step)
                    pa = class_to_circle_pos[held_classes[i]]
                    pb = class_to_circle_pos[held_classes[j]]
                    cw = (pb - pa) % 12; ccw_dist = (pa - pb) % 12
                    if cw <= ccw_dist: lin_geo = cw; lin_dir = 'cw'
                    else: lin_geo = ccw_dist; lin_dir = 'ccw'
                    n_sides = 12 // _m.gcd(lin_geo, 12)
                    pts = []
                    for k in range(n_sides):
                        p = (pa + k * lin_geo) % 12 if lin_dir == 'cw' else (pa - k * lin_geo) % 12
                        c = circle_seq[p]
                        pts.append(node_positions[c])
                    for k in range(n_sides):
                        x0, y0 = pts[k]; x1, y1 = pts[(k + 1) % n_sides]
                        pygame.draw.line(surface, (35, 35, 45), (int(x0), int(y0)), (int(x1), int(y1)), 1)

            # ── 2. styled gradient chords on alpha surface ──
            chord_overlay = pygame.Surface((circle_diam, circle_diam), pygame.SRCALPHA)
            for i in range(n_held):
                for j in range(i + 1, n_held):
                    cl_a = held_classes[i]; cl_b = held_classes[j]
                    step, direction = _compute_generative_step(cl_a, cl_b)
                    style = _STEP_STYLES.get(step, 'solid')
                    style_color = _STEP_COLORS.get(step, (200, 200, 200))

                    ax, ay = node_positions[cl_a]; bx, by = node_positions[cl_b]
                    dx, dy = bx - ax, by - ay
                    dist = _m.hypot(dx, dy)
                    if dist < 1:
                        continue
                    ux, uy = dx / dist, dy / dist
                    nx, ny = -uy, ux
                    start_r = node_radius + 3; end_r = node_radius + 8
                    sx = ax + start_r * ux; sy = ay + start_r * uy
                    ex = bx - end_r * ux; ey = by - end_r * uy
                    chord_dist = _m.hypot(ex - sx, ey - sy)

                    # to circle-local coords
                    lsx = sx - circle_x; lsy = sy - circle_y
                    lex = ex - circle_x; ley = ey - circle_y
                    ldx, ldy = lex - lsx, ley - lsy

                    alpha_a = 160; alpha_b = 200
                    segs = max(2, int(chord_dist / 4))

                    if style == 'double':
                        offset = 2
                        for sign in (-1, 1):
                            for si in range(segs):
                                t0 = si / segs; t1 = (si + 1) / segs
                                x0 = lsx + ldx * t0 + sign * offset * nx
                                y0 = lsy + ldy * t0 + sign * offset * ny
                                x1 = lsx + ldx * t1 + sign * offset * nx
                                y1 = lsy + ldy * t1 + sign * offset * ny
                                h = _arc_hue_chord((t0 + t1) * 0.5, cl_a, cl_b, circle_seq=circle_seq)
                                c = _hsl(h, 100, 50)
                                pygame.draw.line(chord_overlay, (*c, alpha_a),
                                    (int(x0), int(y0)), (int(x1), int(y1)), max(1, 3 - step // 2))
                    elif style == 'solid':
                        for si in range(segs):
                            t0 = si / segs; t1 = (si + 1) / segs
                            x0 = lsx + ldx * t0; y0 = lsy + ldy * t0
                            x1 = lsx + ldx * t1; y1 = lsy + ldy * t1
                            h = _arc_hue_chord((t0 + t1) * 0.5, cl_a, cl_b, circle_seq=circle_seq)
                            c = _hsl(h, 100, 50)
                            w = max(2, 5 - step // 2)
                            pygame.draw.line(chord_overlay, (*c, alpha_a), (int(x0), int(y0)), (int(x1), int(y1)), w)
                    elif style == 'anchored':
                        half_w = max(1, (4 - step // 2))
                        for sign in (-1, 1):
                            ox0 = lsx + sign * half_w * nx; oy0 = lsy + sign * half_w * ny
                            ox1 = lex + sign * half_w * nx; oy1 = ley + sign * half_w * ny
                            h = _arc_hue_chord(0.5, cl_a, cl_b, circle_seq=circle_seq)
                            c = _hsl(h, 100, 50)
                            pygame.draw.line(chord_overlay, (*c, alpha_a), (int(ox0), int(oy0)), (int(ox1), int(oy1)), max(2, half_w))
                        pygame.draw.circle(chord_overlay, (*style_color, alpha_b), (int(lsx), int(lsy)), 3)
                        pygame.draw.circle(chord_overlay, (*style_color, alpha_b), (int(lex), int(ley)), 3)
                    elif style == 'dotted':
                        spacing = 5; n_dots = max(2, int(chord_dist / spacing))
                        for di in range(n_dots + 1):
                            t = di / n_dots
                            x = lsx + ldx * t; y = lsy + ldy * t
                            h = _arc_hue_chord(t, cl_a, cl_b, circle_seq=circle_seq)
                            c = _hsl(h, 100, 50)
                            pygame.draw.circle(chord_overlay, (*c, alpha_a), (int(x), int(y)), max(2, 4 - step // 2))
                    elif style == 'dotdash':
                        dash = 14; gap = 6; dot = 3; dg = 4
                        cycle = dash + gap + dot + dg
                        cyc_n = max(1, int(chord_dist / cycle))
                        for ci in range(cyc_n + 1):
                            t0 = ci * cycle / chord_dist; t1 = min(t0 + dash / chord_dist, 1.0)
                            if t1 > t0:
                                for si in range(max(1, int((t1 - t0) * chord_dist / 3))):
                                    lt = t0 + (t1 - t0) * si / max(1, int((t1 - t0) * chord_dist / 3))
                                    rt = min(t1, lt + (t1 - t0) / max(1, int((t1 - t0) * chord_dist / 3)))
                                    h = _arc_hue_chord((lt + rt) * 0.5, cl_a, cl_b, circle_seq=circle_seq)
                                    c = _hsl(h, 100, 50)
                                    pygame.draw.line(chord_overlay, (*c, alpha_a),
                                        (int(lsx + ldx * lt), int(lsy + ldy * lt)),
                                        (int(lsx + ldx * rt), int(lsy + ldy * rt)), max(2, 4 - step // 2))
                            td = min(t1 + gap / chord_dist, 1.0); t0d = td + dot / chord_dist
                            if t0d > td:
                                t_mid = (td + t0d) * 0.5
                                h = _arc_hue_chord(t_mid, cl_a, cl_b, circle_seq=circle_seq)
                                c = _hsl(h, 100, 50)
                                pygame.draw.circle(chord_overlay, (*c, alpha_a),
                                    (int(lsx + ldx * t_mid), int(lsy + ldy * t_mid)), max(1, 3 - step // 2))
                    elif style == 'longdash':
                        dash_l = 16; gap_l = 8; cycle_l = dash_l + gap_l
                        dn = max(1, int(chord_dist / cycle_l))
                        for di in range(dn):
                            t0 = di * cycle_l / chord_dist; t1 = min(t0 + dash_l / chord_dist, 1.0)
                            if t1 <= t0: continue
                            for si in range(max(1, int((t1 - t0) * chord_dist / 3))):
                                lt = t0 + (t1 - t0) * si / max(1, int((t1 - t0) * chord_dist / 3))
                                rt = min(t1, lt + (t1 - t0) / max(1, int((t1 - t0) * chord_dist / 3)))
                                h = _arc_hue_chord((lt + rt) * 0.5, cl_a, cl_b, circle_seq=circle_seq)
                                c = _hsl(h, 100, 50)
                                pygame.draw.line(chord_overlay, (*c, alpha_a),
                                    (int(lsx + ldx * lt), int(lsy + ldy * lt)),
                                    (int(lsx + ldx * rt), int(lsy + ldy * rt)), max(2, 4 - step // 2))

                    # midpoint indicator dot
                    mx = (lsx + lex) / 2; my = (lsy + ley) / 2
                    h_mid = _arc_hue_chord(0.5, cl_a, cl_b, circle_seq=circle_seq)
                    mid_c = _hsl(h_mid, 100, 75)
                    pygame.draw.circle(chord_overlay, (*mid_c, 220), (int(mx), int(my)), 4)

            surface.blit(chord_overlay, (circle_x, circle_y))
    elif relation_pair and relation_pair.get('left') and relation_pair.get('right'):
        left_cls = relation_pair['left'][0]
        right_cls = relation_pair['right'][0]
        if left_cls != right_cls:
            step, direction = _compute_generative_step(left_cls, right_cls)
            style = _STEP_STYLES.get(step, 'solid')
            step_color = _STEP_COLORS.get(step, (200, 200, 200))

            ax, ay = node_positions[right_cls]
            bx, by = node_positions[left_cls]

            # travel particle always follows pressing order (left_cls → right_cls)
            tr_ax, tr_ay = ax, ay
            tr_bx, tr_by = bx, by

            # reverse chord direction for CCW so arrow matches generative direction
            if direction == 'ccw':
                ax, ay, bx, by = bx, by, ax, ay

            # ── polygon shadow (dim complete shape for this relation step) ──
            pa = class_to_circle_pos[left_cls]
            pb = class_to_circle_pos[right_cls]
            cw = (pb - pa) % 12; ccw = (pa - pb) % 12
            if cw <= ccw: lin_geo = cw; lin_dir = 'cw'
            else: lin_geo = ccw; lin_dir = 'ccw'
            n_sides = 12 // _m.gcd(lin_geo, 12)

            # collect polygon vertices as (cls, x, y)
            pts = []
            for i in range(n_sides):
                if lin_dir == 'cw': p = (pa + i * lin_geo) % 12
                else: p = (pa - i * lin_geo) % 12
                c = circle_seq[p]; px, py = node_positions[c]
                pts.append((c, px, py))

            # draw all polygon edges dimmed (except active chord)
            for i in range(n_sides):
                cl_a, x0, y0 = pts[i]
                cl_b, x1, y1 = pts[(i + 1) % n_sides]
                if {cl_a, cl_b} == {left_cls, right_cls}:
                    continue
                col = (35, 35, 45)
                pygame.draw.line(surface, col, (int(x0), int(y0)), (int(x1), int(y1)), 1)

            # ── active gradient chord (drawn on top of shadow) ──
            dx, dy = ax - bx, ay - by
            dist = _m.hypot(dx, dy)
            if dist > 0:
                ux, uy = dx / dist, dy / dist
                nx, ny = -uy, ux

                ang_arrow = _m.atan2(ay - by, ax - bx)
                tip_x = ax - (node_radius + 8) * _m.cos(ang_arrow)
                tip_y = ay - (node_radius + 8) * _m.sin(ang_arrow)
                start_x = bx + (node_radius + 3) * _m.cos(ang_arrow)
                start_y = by + (node_radius + 3) * _m.sin(ang_arrow)
                chord_dist = _m.hypot(tip_x - start_x, tip_y - start_y)

                if style == 'double':
                    offset = 3
                    segs = max(2, int(chord_dist / 2))
                    for sign in (-1, 1):
                        ox0 = start_x + sign * offset * nx
                        oy0 = start_y + sign * offset * ny
                        ox1 = tip_x + sign * offset * nx
                        oy1 = tip_y + sign * offset * ny
                        for si in range(segs):
                            t0 = si / segs; t1 = (si + 1) / segs
                            sx0 = ox0 + (ox1 - ox0) * t0; sy0 = oy0 + (oy1 - oy0) * t0
                            sx1 = ox0 + (ox1 - ox0) * t1; sy1 = oy0 + (oy1 - oy0) * t1
                            h = _arc_hue_chord((t0 + t1) * 0.5, left_cls, right_cls, circle_seq=circle_seq)
                            c = _hsl(h, 100, 50)
                            pygame.draw.line(surface, c, (int(sx0), int(sy0)), (int(sx1), int(sy1)),
                                           max(1, 3 - step // 2))
                    _draw_arrow_tip(surface, step_color, (tip_x, tip_y), ang_arrow, size=9)
                elif style == 'solid':
                    segs = max(2, int(chord_dist / 2))
                    for si in range(segs):
                        t0 = si / segs; t1 = (si + 1) / segs
                        sx0 = start_x + (tip_x - start_x) * t0
                        sy0 = start_y + (tip_y - start_y) * t0
                        sx1 = start_x + (tip_x - start_x) * t1
                        sy1 = start_y + (tip_y - start_y) * t1
                        h = _arc_hue_chord((t0 + t1) * 0.5, left_cls, right_cls, circle_seq=circle_seq)
                        c = _hsl(h, 100, 50)
                        w = max(2, 5 - step // 2)
                        pygame.draw.line(surface, c, (int(sx0), int(sy0)), (int(sx1), int(sy1)), w)
                    _draw_arrow_tip(surface, step_color, (tip_x, tip_y), ang_arrow, size=9)
                elif style == 'anchored':
                    half_w = max(2, (6 - step // 2))
                    for sign in (-1, 1):
                        ox0 = start_x + sign * half_w * nx; oy0 = start_y + sign * half_w * ny
                        ox1 = tip_x + sign * half_w * nx; oy1 = tip_y + sign * half_w * ny
                        pygame.draw.line(surface, step_color, (int(ox0), int(oy0)),
                                       (int(ox1), int(oy1)), max(2, half_w))
                    pygame.draw.circle(surface, step_color, (int(start_x), int(start_y)), 4)
                    pygame.draw.circle(surface, step_color, (int(tip_x), int(tip_y)), 4)
                else:
                    w = max(2, 5 - step // 2)
                    cl = _m.hypot(tip_x - start_x, tip_y - start_y)
                    if cl > 0:
                        if style == 'dotted':
                            spacing = 4
                            n = max(2, int(cl / spacing))
                            for i in range(n + 1):
                                t = i / n
                                x = start_x + (tip_x - start_x) * t
                                y = start_y + (tip_y - start_y) * t
                                h = _arc_hue_chord(t, left_cls, right_cls, circle_seq=circle_seq)
                                pygame.draw.circle(surface, _hsl(h, 100, 50), (int(x), int(y)), w)
                        elif style == 'dotdash':
                            seg = 12; seg_n = max(1, int(cl / seg))
                            for i in range(seg_n):
                                t0 = i * seg / cl; t1 = min((i + 1) * seg / cl, 1.0)
                                if i % 2 == 0:
                                    sn = max(1, int((t1 - t0) * cl / 2))
                                    for s in range(sn):
                                        lt = t0 + (t1 - t0) * s / sn; rt = t0 + (t1 - t0) * (s + 1) / sn
                                        h = _arc_hue_chord((lt + rt) * 0.5, left_cls, right_cls, circle_seq=circle_seq)
                                        c = _hsl(h, 100, 50)
                                        pygame.draw.line(surface, c,
                                            (int(start_x + (tip_x - start_x) * lt), int(start_y + (tip_y - start_y) * lt)),
                                            (int(start_x + (tip_x - start_x) * rt), int(start_y + (tip_y - start_y) * rt)), w)
                                else:
                                    t = (t0 + t1) * 0.5
                                    h = _arc_hue_chord(t, left_cls, right_cls, circle_seq=circle_seq)
                                    x = start_x + (tip_x - start_x) * t; y = start_y + (tip_y - start_y) * t
                                    pygame.draw.circle(surface, _hsl(h, 100, 50), (int(x), int(y)), w)
                        elif style == 'longdash':
                            dash = 14; gap = 8; cycle = dash + gap
                            dn = max(1, int(cl / cycle))
                            for i in range(dn):
                                t0 = i * cycle / cl; t1 = min(t0 + dash / cl, 1.0)
                                if t1 <= t0: continue
                                sn = max(1, int((t1 - t0) * cl / 2))
                                for s in range(sn):
                                    lt = t0 + (t1 - t0) * s / sn; rt = t0 + (t1 - t0) * (s + 1) / sn
                                    h = _arc_hue_chord((lt + rt) * 0.5, left_cls, right_cls, circle_seq=circle_seq)
                                    c = _hsl(h, 100, 50)
                                    pygame.draw.line(surface, c,
                                        (int(start_x + (tip_x - start_x) * lt), int(start_y + (tip_y - start_y) * lt)),
                                        (int(start_x + (tip_x - start_x) * rt), int(start_y + (tip_y - start_y) * rt)), w)
                    _draw_arrow_tip(surface, step_color, (tip_x, tip_y), ang_arrow, size=9)

            # ── travel particle (light travelling in pressing order) ──
            if _relation_anim['travel_active'] and _relation_anim['travel_progress'] > 0:
                tp = _relation_anim['travel_progress']
                tr_ang = _m.atan2(tr_ay - tr_by, tr_ax - tr_bx)
                tr_st_x = tr_bx + (node_radius + 3) * _m.cos(tr_ang)
                tr_st_y = tr_by + (node_radius + 3) * _m.sin(tr_ang)
                tr_tp_x = tr_ax - (node_radius + 8) * _m.cos(tr_ang)
                tr_tp_y = tr_ay - (node_radius + 8) * _m.sin(tr_ang)
                px = tr_st_x + (tr_tp_x - tr_st_x) * tp
                py = tr_st_y + (tr_tp_y - tr_st_y) * tp
                pc = _hsl(_arc_hue_chord(tp, left_cls, right_cls, circle_seq=circle_seq), 100, 75)
                for r in range(14, 3, -2):
                    alpha = int(120 * (1 - r / 14))
                    glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                    pygame.draw.circle(glow, (*pc, alpha), (r, r), r)
                    surface.blit(glow, (int(px) - r, int(py) - r))
                pygame.draw.circle(surface, (255, 255, 255), (int(px), int(py)), 5)
                pygame.draw.circle(surface, pc, (int(px), int(py)), 7, 1)

    # ═══════════════════════════════════════════
    # BIG BOX — pair visualizer (normal) or chord analysis (chords mode)
    # ═══════════════════════════════════════════
    box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    box_surf.fill((16, 16, 22, 230))
    pygame.draw.rect(box_surf, (50, 50, 60), (0, 0, box_w, box_h), 1, border_radius=8)
    surface.blit(box_surf, (box_x, box_y))

    if chords_mode:
        held_classes = sorted(active_classes.keys())
        n_held = len(held_classes)
        title_r = fonts['xs'].render(f"CHORDS MODE — {n_held} notes pressed", True, (140, 140, 150))
        surface.blit(title_r, (box_x + box_w // 2 - title_r.get_width() // 2, box_y - 16))

        if n_held == 0:
            idle = fonts['xs'].render("play notes to form a chord", True, (60, 60, 60))
            surface.blit(idle, (box_x + (box_w - idle.get_width()) // 2, box_y + box_h // 2 - 8))
        elif n_held == 1:
            cls = held_classes[0]
            color = active_classes[cls]
            # compact single card
            cd_w = min(100, box_w - 24); cd_h = min(90, box_h - 24)
            _draw_compact_chord_card(surface, fonts, box_x + 12, box_y + 12, cd_w, cd_h, cls, color)
            hint = fonts['xs'].render("add more notes to see relationships", True, (70, 70, 70))
            surface.blit(hint, (box_x + (box_w - hint.get_width()) // 2, box_y + box_h - 28))
        else:
            # compact card rows — show each held note as a small colored card
            max_card_w = 70; gap = 4
            cards_per_row = max(1, (box_w - 24 + gap) // (max_card_w + gap))
            row_card_w = min(max_card_w, (box_w - 24 - gap * (min(n_held, cards_per_row) - 1)) // min(n_held, cards_per_row))
            card_h = max(44, min(60, int((box_h - 120) / max(1, (n_held + cards_per_row - 1) // cards_per_row))))
            card_y_start = box_y + 12
            info_base_y = card_y_start + ((n_held + cards_per_row - 1) // cards_per_row) * (card_h + 3) + 6

            for idx, cls in enumerate(held_classes):
                row = idx // cards_per_row; col = idx % cards_per_row
                cx = box_x + 12 + col * (row_card_w + gap)
                cy = card_y_start + row * (card_h + 3)
                color = active_classes[cls]
                _draw_compact_chord_card(surface, fonts, int(cx), int(cy), int(row_card_w), int(card_h), cls, color)

            # n-gon analysis below cards
            from collections import Counter
            step_counts = Counter()
            for i in range(n_held):
                for j in range(i + 1, n_held):
                    step, _ = _compute_generative_step(held_classes[i], held_classes[j])
                    step_counts[step] += 1
            unique_steps = sorted(step_counts.keys())
            line_y = info_base_y
            max_lines = (box_y + box_h - line_y - 26) // 15
            for si in range(min(len(unique_steps), max_lines)):
                step = unique_steps[si]
                step_name = _STEP_NAMES.get(step, f"±{step}")
                n_pairs = step_counts[step]
                style_color = _STEP_COLORS.get(step, (160, 160, 160))
                n_sides = 12 // _m.gcd(step, 12) if step > 0 else 0
                if n_sides == 12: shape = "starburst"
                elif n_sides == 6: shape = "hexagon"
                elif n_sides == 4: shape = "square"
                elif n_sides == 3: shape = "triangle"
                elif n_sides == 2: shape = "midpoint line"
                else: shape = f"{n_sides}-gon"
                info_str = f"{step_name}  —  {n_pairs} pair(s)  →  {shape}"
                info = fonts['xs'].render(info_str, True, style_color)
                surface.blit(info, (box_x + 12, int(line_y)))
                line_y += 15
            total_pairs = n_held * (n_held - 1) // 2
            summary = fonts['xs'].render(f"Total: {n_held} notes, {total_pairs} relations, {len(unique_steps)} step types",
                                        True, (100, 100, 100))
            surface.blit(summary, (box_x + 12, int(line_y) + 2))
    else:
        title_r = fonts['xs'].render("NOTE RELATION", True, (140, 140, 150))
        surface.blit(title_r, (box_x + box_w // 2 - title_r.get_width() // 2, box_y - 16))

        left_entry = relation_pair['left'] if relation_pair else None
        right_entry = relation_pair['right'] if relation_pair else None

        # card dimensions — compact cards, generous gap for visible arrow
        card_w = int((box_w - 100) * 0.34)
        card_h = min(110, box_h - 110)
        card_y = box_y + 18

        l_cx = box_x + 12
        r_cx = box_x + box_w - 12 - card_w

        # ── left card ──
        if left_entry:
            l_cls, l_midi, l_color, l_label, l_v = left_entry
            l_freq = midi_to_freq(l_midi)
            _draw_note_card(surface, fonts, l_cx, card_y, card_w, card_h,
                           l_cls, l_label, l_color, l_freq)
        else:
            _draw_empty_card(surface, fonts, l_cx, card_y, card_w, card_h, "play a note...")

        # ── right card ──
        if right_entry:
            r_cls, r_midi, r_color, r_label, r_v = right_entry
            r_freq = midi_to_freq(r_midi)
            _draw_note_card(surface, fonts, r_cx, card_y, card_w, card_h,
                           r_cls, r_label, r_color, r_freq)
        else:
            _draw_empty_card(surface, fonts, r_cx, card_y, card_w, card_h, "play next note")

        # ── connecting line + arrow (left → right direction) ──
        conn_y = card_y + card_h // 2
        l_edge_x = l_cx + card_w + 4
        r_edge_x = r_cx - 4
        conn_gap = r_edge_x - l_edge_x
        info_base_y = card_y + card_h + 8

        if left_entry and right_entry:
            if l_cls != r_cls:
                step, direction = _compute_generative_step(l_cls, r_cls)
            else:
                step, direction = 0, 'same'
            fsign = 1.0 if direction == 'cw' else -1.0
            style = _STEP_STYLES.get(step, 'solid')
            style_color = _STEP_COLORS.get(step, (180, 180, 180))
            l_oct = l_midi // 12 - 1
            r_oct = r_midi // 12 - 1

            # gradient styled line spanning the full gap between cards
            if style == 'double':
                offset = 3
                seg_count = max(2, conn_gap // 2)
                for sign in (-1, 1):
                    px_prev = l_edge_x
                    for s_idx in range(1, seg_count + 1):
                        t = s_idx / seg_count
                        px = l_edge_x + conn_gap * t
                        h = _arc_hue_chord(t, l_cls, r_cls, flow_sign=fsign, circle_seq=circle_seq)
                        seg_col = _hsl(h, 100, 50)
                        pygame.draw.line(surface, seg_col,
                            (int(px_prev), int(conn_y + sign * offset)),
                            (int(px), int(conn_y + sign * offset)), max(1, 3 - step // 2))
                        px_prev = px
            elif style == 'solid':
                seg_count = max(2, conn_gap // 2)
                px_prev = l_edge_x
                for s_idx in range(1, seg_count + 1):
                    t = s_idx / seg_count
                    px = l_edge_x + conn_gap * t
                    h = _arc_hue_chord(t, l_cls, r_cls, flow_sign=fsign, circle_seq=circle_seq)
                    seg_col = _hsl(h, 100, 50)
                    w = max(2, 5 - step // 2)
                    pygame.draw.line(surface, seg_col,
                        (int(px_prev), int(conn_y)), (int(px), int(conn_y)), w)
                    px_prev = px
            elif style == 'anchored':
                half_w = max(2, (6 - step // 2))
                for sign in (-1, 1):
                    pygame.draw.line(surface, style_color,
                        (int(l_edge_x), int(conn_y + sign * half_w)),
                        (int(r_edge_x), int(conn_y + sign * half_w)), max(2, half_w))
                pygame.draw.circle(surface, style_color, (int(l_edge_x), int(conn_y)), 4)
                pygame.draw.circle(surface, style_color, (int(r_edge_x), int(conn_y)), 4)
            else:
                w = max(2, 5 - step // 2)
                if style == 'dotted':
                    spacing = 4; n = max(2, int(conn_gap / spacing))
                    for i in range(n + 1):
                        t = i / n
                        h = _arc_hue_chord(t, l_cls, r_cls, flow_sign=fsign, circle_seq=circle_seq)
                        pygame.draw.circle(surface, _hsl(h, 100, 50), (int(l_edge_x + conn_gap * t), int(conn_y)), w)
                elif style == 'dotdash':
                    seg = 12; seg_n = max(1, int(conn_gap / seg))
                    for i in range(seg_n):
                        t0 = i * seg / conn_gap; t1 = min((i + 1) * seg / conn_gap, 1.0)
                        if i % 2 == 0:
                            sn = max(1, int((t1 - t0) * conn_gap / 2))
                            for s in range(sn):
                                lt = t0 + (t1 - t0) * s / sn; rt = t0 + (t1 - t0) * (s + 1) / sn
                                h = _arc_hue_chord((lt + rt) * 0.5, l_cls, r_cls, flow_sign=fsign, circle_seq=circle_seq)
                                pygame.draw.line(surface, _hsl(h, 100, 50),
                                    (int(l_edge_x + conn_gap * lt), int(conn_y)),
                                    (int(l_edge_x + conn_gap * rt), int(conn_y)), w)
                        else:
                            t = (t0 + t1) * 0.5
                            h = _arc_hue_chord(t, l_cls, r_cls, flow_sign=fsign, circle_seq=circle_seq)
                            pygame.draw.circle(surface, _hsl(h, 100, 50), (int(l_edge_x + conn_gap * t), int(conn_y)), w)
                elif style == 'longdash':
                    dash = 14; gap = 8; cycle = dash + gap
                    dn = max(1, int(conn_gap / cycle))
                    for i in range(dn):
                        t0 = i * cycle / conn_gap; t1 = min(t0 + dash / conn_gap, 1.0)
                        if t1 <= t0: continue
                        sn = max(1, int((t1 - t0) * conn_gap / 2))
                        for s in range(sn):
                            lt = t0 + (t1 - t0) * s / sn; rt = t0 + (t1 - t0) * (s + 1) / sn
                            h = _arc_hue_chord((lt + rt) * 0.5, l_cls, r_cls, flow_sign=fsign, circle_seq=circle_seq)
                            pygame.draw.line(surface, _hsl(h, 100, 50),
                                (int(l_edge_x + conn_gap * lt), int(conn_y)),
                                (int(l_edge_x + conn_gap * rt), int(conn_y)), w)

            # directional arrow — CW: right end pointing right, CCW: left end pointing left
            if step != 6:
                if direction == 'cw':
                    _draw_arrow_tip(surface, style_color, (r_edge_x - 2, conn_y), 0, size=8)
                else:
                    _draw_arrow_tip(surface, style_color, (l_edge_x + 2, conn_y), _m.pi, size=8)

            # ── relation info line below cards ──
            if step > 0:
                step_name = _STEP_NAMES.get(step, f"±{step}")
                octave_diff = r_oct - l_oct
                if octave_diff > 0: oct_str = f"+{octave_diff} oct"
                elif octave_diff < 0: oct_str = f"{octave_diff} oct"
                else: oct_str = "0 oct"

                if direction == 'cw': dir_str = "→ CW"
                elif direction == 'ccw': dir_str = "← CCW"
                else: dir_str = ""

                info_str = f"{step_name}  {dir_str}  {oct_str}"
                info = fonts['xs'].render(info_str, True, style_color)
                surface.blit(info, (box_x + (box_w - info.get_width()) // 2, info_base_y))

                if octave_diff > 0:
                    _draw_up_arrow(surface, style_color,
                                  (box_x + box_w // 2 + info.get_width() // 2 + 12, info_base_y + 6), size=6)
                elif octave_diff < 0:
                    _draw_down_arrow(surface, style_color,
                                    (box_x + box_w // 2 + info.get_width() // 2 + 12, info_base_y + 6), size=6)
        else:
            idle = fonts['xs'].render("play two notes to see relationship", True, (60, 60, 60))
            surface.blit(idle, (box_x + (box_w - idle.get_width()) // 2, conn_y - 8))

    # ═══════════════════════════════════════════
    # BOTTOM SLOTS — highlight + generative sequence row
    # ═══════════════════════════════════════════
    slot_w = content_w / _REL_SLOTS
    slots = _build_relations_slots()

    # highlight rectangles (scaled down height)
    for i, (g_class, _) in enumerate(slots):
        if g_class not in active_classes:
            continue
        color = active_classes[g_class]
        hx = int(content_x + i * slot_w + 1)
        hw = max(1, int(slot_w) - 2)
        pygame.draw.rect(surface, color, (hx, highlight_y, hw, highlight_h))
        pygame.draw.rect(surface, (255, 255, 255), (hx, highlight_y, hw, highlight_h), 1)

    pygame.draw.line(surface, (45, 45, 45), (content_x, slot_y - _REL_HIGHLIGHT_GAP),
                     (content_x + content_w, slot_y - _REL_HIGHLIGHT_GAP), 1)
    pygame.draw.rect(surface, (18, 18, 18), (content_x, slot_y, content_w, _REL_SLOT_H))
    pygame.draw.line(surface, (45, 45, 45), (content_x, slot_y),
                     (content_x + content_w, slot_y), 1)

    for i, (g_class, is_central) in enumerate(slots):
        sx = int(content_x + i * slot_w + 1)
        sw = max(1, int(slot_w) - 2)
        sy = slot_y + _REL_SLOT_LABEL_H
        sh = _REL_SLOT_RECT_H
        is_active = g_class in active_classes
        label_text = f"G{g_class}"
        lbl = fonts['xs'].render(label_text, True, (120, 120, 120) if is_central else (50, 50, 50))
        lbl_x = sx + sw // 2 - lbl.get_width() // 2
        lbl_y = slot_y + (_REL_SLOT_LABEL_H - lbl.get_height()) // 2
        surface.blit(lbl, (lbl_x, lbl_y))

        if is_central:
            if is_active:
                color = active_classes[g_class]
                pygame.draw.rect(surface, color, (sx, sy, sw, sh))
                pygame.draw.rect(surface, (255, 255, 255), (sx, sy, sw, sh), 1)
            else:
                pygame.draw.rect(surface, (28, 28, 28), (sx, sy, sw, sh))
                pygame.draw.rect(surface, (55, 55, 55), (sx, sy, sw, sh), 1)
        else:
            if is_active:
                color = active_classes[g_class]
                grey = int(round((color[0] + 40) * 0.33))
                grey_c = (max(0, min(255, grey)), max(0, min(255, int(grey * 0.9))),
                          max(0, min(255, int(grey * 0.8))))
                pygame.draw.rect(surface, grey_c, (sx, sy, sw, sh))
                pygame.draw.rect(surface, (80, 80, 80), (sx, sy, sw, sh), 1)
            else:
                pygame.draw.rect(surface, (20, 20, 20), (sx, sy, sw, sh))
                pygame.draw.rect(surface, (32, 32, 32), (sx, sy, sw, sh), 1)


def _draw_compact_chord_card(surface, fonts, cx, cy, w, h, note_class, color):
    """Compact card showing G-class color swatch and label — for chords mode."""
    r = 4
    pygame.draw.rect(surface, (22, 22, 32), (cx, cy, w, h), border_radius=r)
    pygame.draw.rect(surface, (60, 60, 70), (cx, cy, w, h), 1, border_radius=r)
    swatch_s = min(w - 12, h - 18, 30)
    swatch_s = max(swatch_s, 10)
    sx = cx + (w - swatch_s) // 2
    sy = cy + 6
    pygame.draw.rect(surface, color, (sx, sy, swatch_s, swatch_s), border_radius=3)
    pygame.draw.rect(surface, (200, 200, 200), (sx, sy, swatch_s, swatch_s), 1, border_radius=3)
    lbl_y = sy + swatch_s + 2
    if lbl_y + 14 <= cy + h:
        lbl = fonts['xs'].render(f"G{note_class}", True, (220, 220, 220))
        surface.blit(lbl, (cx + (w - lbl.get_width()) // 2, lbl_y))


def _draw_note_card(surface, fonts, cx, cy, w, h, note_class, label, color, freq):
    """Draw a single note card at (cx, cy) with size w×h."""
    r = 6
    pygame.draw.rect(surface, (22, 22, 32), (cx, cy, w, h), border_radius=r)
    pygame.draw.rect(surface, (60, 60, 70), (cx, cy, w, h), 1, border_radius=r)
    # color swatch
    swatch_s = min(36, w - 16)
    sx = cx + (w - swatch_s) // 2
    sy = cy + 10
    pygame.draw.rect(surface, color, (sx, sy, swatch_s, swatch_s), border_radius=4)
    pygame.draw.rect(surface, (200, 200, 200), (sx, sy, swatch_s, swatch_s), 1, border_radius=4)
    # label
    txt_y = sy + swatch_s + 6
    cls_lbl = fonts['xs'].render(f"G{note_class}", True, (220, 220, 220))
    surface.blit(cls_lbl, (cx + (w - cls_lbl.get_width()) // 2, txt_y))
    midi_lbl = fonts['xs'].render(label, True, (180, 180, 180))
    surface.blit(midi_lbl, (cx + (w - midi_lbl.get_width()) // 2, txt_y + 16))
    freq_lbl = fonts['xs'].render(f"{freq:.1f} Hz", True, (120, 120, 120))
    surface.blit(freq_lbl, (cx + (w - freq_lbl.get_width()) // 2, txt_y + 32))


def _draw_empty_card(surface, fonts, cx, cy, w, h, hint_text):
    """Draw an empty placeholder card."""
    r = 6
    pygame.draw.rect(surface, (18, 18, 24), (cx, cy, w, h), border_radius=r)
    pygame.draw.rect(surface, (40, 40, 50), (cx, cy, w, h), 1, border_radius=r)
    hint = fonts['xs'].render(hint_text, True, (50, 50, 55))
    surface.blit(hint, (cx + (w - hint.get_width()) // 2, cy + h // 2 - hint.get_height() // 2))


def draw_piano_roll_nodes(surface, fonts, note_states, node_trail,
                          content_x, content_w, W, H, bg,
                          palette_pick=None):
    """Draw the nodes view: fixed-size circles connected by gradient lines."""
    trail_area_top = VIEW_TAB_H + SUB_TAB_H
    trail_area_bot = H - SQUARE_ROW_H
    trail_area_h   = trail_area_bot - trail_area_top

    sq_w = content_w / PIANO_NOTE_COUNT
    palette_pick = palette_pick or set()

    # Build set of currently held semitones for octave highlight
    held_semitones = set()
    for midi_note, ns in note_states.items():
        if ns.get('held'):
            held_semitones.add((midi_note - 60) % 12)

    # ── clipping ────
    clip = pygame.Rect(content_x, trail_area_top, content_w, trail_area_h)
    old_clip = surface.get_clip()
    surface.set_clip(clip)

    # ── draw connecting lines first (behind nodes) ────
    for i in range(1, len(node_trail)):
        n0 = node_trail[i - 1]
        n1 = node_trail[i]
        x0, y0 = int(n0['cx']), int(n0['cy'])
        x1, y1 = int(n1['cx']), int(n1['cy'])
        segments = max(1, int(math.hypot(x1 - x0, y1 - y0) / 3))
        for s in range(segments):
            t0 = s / segments
            t1 = (s + 1) / segments
            sx0 = int(x0 + (x1 - x0) * t0)
            sy0 = int(y0 + (y1 - y0) * t0)
            sx1 = int(x0 + (x1 - x0) * t1)
            sy1 = int(y0 + (y1 - y0) * t1)
            col = lerp_c(n0['color'], n1['color'], (t0 + t1) / 2)
            pygame.draw.line(surface, col, (sx0, sy0), (sx1, sy1), 2)

    # ── draw nodes ────
    for node in node_trail:
        cx, cy = int(node['cx']), int(node['cy'])
        midi = node.get('midi_note')
        semi = (midi - 60) % 12 if midi is not None else None
        is_palette_node = (palette_pick and semi in palette_pick)
        if is_palette_node:
            pygame.draw.circle(surface, node['color'], (cx, cy), NODE_RADIUS)
            pygame.draw.circle(surface, (180, 160, 100), (cx, cy), NODE_RADIUS + 2, 1)
        else:
            pygame.draw.circle(surface, node['color'], (cx, cy), NODE_RADIUS)
            pygame.draw.circle(surface, (200, 200, 200), (cx, cy), NODE_RADIUS, 1)

    surface.set_clip(old_clip)

    # ── separator line ────
    pygame.draw.line(surface, (45, 45, 45),
                    (content_x, trail_area_bot),
                    (content_x + content_w, trail_area_bot), 1)
    ticks = pygame.time.get_ticks()
    for idx in range(PIANO_NOTE_COUNT):
        midi_note = PIANO_MIDI_MIN + idx
        sx  = content_x + idx * sq_w
        sw  = max(1.0, sq_w - 1.0)
        sy  = trail_area_bot + 3
        sh  = SQUARE_ROW_H - 6
        semi = (midi_note - 60) % 12
        is_palette = (palette_pick and semi in palette_pick)

        ns = note_states.get(midi_note)
        is_held_octave = semi in held_semitones
        if ns and ns.get('held'):
            blink      = (math.sin(ticks * 0.025) + 1) / 2
            brightness = 0.55 + 0.45 * blink
            r, g, b    = ns['color']
            color      = (int(r * brightness), int(g * brightness), int(b * brightness))
            pygame.draw.rect(surface, color,
                    (int(sx), int(sy), int(sw), int(sh)), border_radius=2)
            border = (255, 200, 60) if is_palette else (200, 200, 200)
            pygame.draw.rect(surface, border,
                    (int(sx), int(sy), int(sw), int(sh)), 1, border_radius=2)
            lbl = fonts['xs'].render(ns['label'], True, (220, 220, 220))
            bx = int(sx) + (int(sw) - lbl.get_width()) // 2
            by = int(sy) + (int(sh) - lbl.get_height()) // 2
            surface.blit(lbl, (bx, by))
        else:
            if is_held_octave:
                glow_surf = pygame.Surface((int(sw), trail_area_h + sh), pygame.SRCALPHA)
                r, g, b = ns['color'] if ns else get_color(midi_note)[0]
                for gy in range(trail_area_h + sh):
                    t = gy / (trail_area_h + sh)
                    alpha = int(120 * (1.0 - t))
                    pygame.draw.line(glow_surf, (r, g, b, alpha), (0, gy), (int(sw), gy))
                surface.blit(glow_surf, (int(sx), trail_area_top))
                pygame.draw.rect(surface, (r, g, b),
                        (int(sx), int(sy), int(sw), int(sh)), border_radius=2)
                pygame.draw.rect(surface, (255, 255, 255),
                        (int(sx), int(sy), int(sw), int(sh)), 2, border_radius=2)
            elif is_palette:
                pygame.draw.rect(surface, (45, 40, 30),
                        (int(sx), int(sy), int(sw), int(sh)), border_radius=2)
                pygame.draw.rect(surface, (120, 100, 50),
                        (int(sx), int(sy), int(sw), int(sh)), 1, border_radius=2)
            else:
                pygame.draw.rect(surface, (28, 28, 28),
                        (int(sx), int(sy), int(sw), int(sh)), border_radius=2)
                pygame.draw.rect(surface, (55, 55, 55),
                        (int(sx), int(sy), int(sw), int(sh)), 1, border_radius=2)

    # ── vertical lane grid lines ────
    for idx in range(1, PIANO_NOTE_COUNT):
        gx = content_x + idx * sq_w
        semi = (PIANO_MIDI_MIN + idx - 60) % 12
        if semi in held_semitones:
            color, _, _, _ = get_color(PIANO_MIDI_MIN + idx)
            pygame.draw.line(surface, color, (int(gx), trail_area_top), (int(gx), H), 2)
        elif palette_pick and semi in palette_pick:
            pygame.draw.line(surface, (80, 70, 40), (int(gx), trail_area_top), (int(gx), H), 1)
        else:
            pygame.draw.line(surface, (60, 60, 60), (int(gx), trail_area_top), (int(gx), H), 1)

    # ── idle hint ────
    if not node_trail and not note_states:
        cx   = content_x + content_w // 2
        idle = fonts['sm'].render("play a note...", True, (50, 50, 50))
        surface.blit(idle, (cx - idle.get_width() // 2,
                    trail_area_top + trail_area_h // 2 - 10))
