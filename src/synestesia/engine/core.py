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

SEM = {i: LFI_DATA[i] for i in range(12)}

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
    v = SEM[s][3]
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
    entry = SEM[semitone]
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
    octv = m // 12 - 1
    lfi = LFI_DATA[sem][1]
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
    labels = ["TILES", "NODES"]
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
