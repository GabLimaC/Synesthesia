#!/usr/bin/env python3
"""
Synesthesia Composer + Live MIDI — piano-roll composer with real-time MIDI input.
Liminal Flow Intonation color system.

Controls:
  LEFT-CLICK on grid    → place note
  SHIFT+CLICK on node   → palette-pick its semitone
  ALT+CLICK on node     → toggle connection to next node in hand group
  RIGHT-CLICK on node   → delete
  DRAG a node           → move it
  CTRL+drag             → pan canvas vertically
  MOUSE WHEEL           → scroll
  CTRL+WHEEL            → zoom
  SPACE                 → play / pause
  R                     → reverse
  S                     → stop & reset
  ↑↓                    → BPM ±5
  M                     → mute toggle
  ESC                   → quit
  MIDI button           → import from .mid file
"""

import pygame
import pygame.midi
import math
from ..engine import (
    note_color, lerp_c, mk_sound, name, black, import_midi,
    Note, MI_LO, MI_HI, N_COUNT, TOTAL_BEATS, DEF_BPM,
    NR, NGR, KB_H, TB_H, BG, GRID_BG, LFI_DATA,
)

# ── mutable settings ──────────────────────
SETTINGS = {"min_l": 20.0, "max_l": 80.0}

# ── helpers ───────────────────────────────
def draw_rounded(surf, color, rect, r):
    pygame.draw.rect(surf, color, rect, border_radius=r)

# ── composer state ────────────────────────
class Comp:
    def __init__(self):
        self.notes = []
        self.bpm = DEF_BPM
        self.playing = False
        self.reverse = False
        self.playhead = 0.0
        self.scroll_y = 0.0
        self.beat_h = 40.0
        self.drag_idx = None
        self.drag_off = (0, 0)
        self.panning = False
        self.pan_y = 0
        self.vol = 0.8
        self.palette_pick = set()
        self.muted = False
        self.hand_visible = {'left': True, 'right': True, None: True}
        self.hand_muted = {'left': False, 'right': False, None: False}
        # hidden connections: set of (note_index_a, note_index_b) tuples, a < b
        self.hidden_connections = set()
        # live MIDI state: midi_note -> {color, alpha}
        self.live_notes = {}

    def sorted(self): return sorted(self.notes, key=lambda x: (x.beat, x.midi))

    def note_at(self, sx, sy, gr):
        gx, gy, gw, gh = gr
        best, best_d = None, NGR + 1
        for i, n in enumerate(self.notes):
            nx, ny = self._n2s(n, gr)
            d = math.hypot(sx - nx, sy - ny)
            if d < best_d: best_d = d; best = i
        return best

    def _n2s(self, n, gr):
        gx, gy, gw, gh = gr
        cw = gw / N_COUNT
        nx = gx + (n.midi - MI_LO + .5) * cw
        ny = gy + gh - (n.beat * self.beat_h - self.scroll_y)
        return nx, ny

    def s2n(self, sx, sy, gr):
        gx, gy, gw, gh = gr
        cw = gw / N_COUNT
        m = int((sx - gx) / cw) + MI_LO
        m = max(MI_LO, min(MI_HI, m))
        b = (gh - (sy - gy) + self.scroll_y) / self.beat_h
        b = round(b * 4) / 4
        b = max(0, min(TOTAL_BEATS - .25, b))
        return m, b

    def max_scroll(self, gh):
        return max(0, TOTAL_BEATS * self.beat_h - gh)

    def sounding_indices(self, beat):
        return [i for i, n in enumerate(self.notes) if n.beat <= beat < n.beat + 0.5]

    def visible_notes(self):
        return [n for n in self.notes if self.hand_visible.get(n.hand, True)]

    def audible_notes(self):
        return [n for n in self.notes if not self.hand_muted.get(n.hand, False)]

    def connection_key(self, idx_a, idx_b):
        """Return canonical (min, max) tuple for a connection between two note indices."""
        return (min(idx_a, idx_b), max(idx_a, idx_b))

    def toggle_connection(self, idx_a, idx_b):
        key = self.connection_key(idx_a, idx_b)
        if key in self.hidden_connections:
            self.hidden_connections.discard(key)
        else:
            self.hidden_connections.add(key)

    def is_connection_visible(self, idx_a, idx_b):
        return self.connection_key(idx_a, idx_b) not in self.hidden_connections


# ── drawing ───────────────────────────────
def draw_toolbar(surf, font, comp, W):
    pygame.draw.rect(surf, (18, 18, 26), (0, 0, W, TB_H))
    pygame.draw.line(surf, (40, 40, 55), (0, TB_H), (W, TB_H), 1)

    btns = {}; x = 12; by = 9; bh = 34
    if comp.playing:
        BUTTONS = [
            ('play',  'PAUSE', (220, 190, 60)),
            ('stop',  'STOP',  (210, 85, 85)),
        ]
    else:
        BUTTONS = [
            ('play',  'PLAY',  (70, 210, 100)),
            ('stop',  'STOP',  (210, 85, 85)),
        ]
    BUTTONS += [
        ('rev',   'REV',   (100, 160, 240)),
        ('reset', 'RESET', (170, 170, 130)),
        ('clear', 'CLEAR', (190, 100, 100)),
        ('midi',  'MIDI',  (120, 190, 120)),
    ]
    # Mute toggle
    mute_col = (210, 85, 85) if comp.muted else (100, 180, 100)
    mute_lbl = 'MUTED' if comp.muted else 'MUTE'
    BUTTONS.append(('mute', mute_lbl, mute_col))

    # Hand visibility / mute toggles
    for hand, label in (('left', 'LH'), ('right', 'RH')):
        vis = comp.hand_visible.get(hand, True)
        mut = comp.hand_muted.get(hand, False)
        if not vis:
            col = (80, 80, 80)
            lbl = f'{label} HID'
        elif mut:
            col = (210, 85, 85)
            lbl = f'{label} MUT'
        else:
            col = (100, 180, 100)
            lbl = label
        BUTTONS.append((f'{hand}_toggle', lbl, col))

    for bid, label, col in BUTTONS:
        txt = font.render(label, True, col)
        bw = max(74, txt.get_width() + 20)
        r = pygame.Rect(x, by, bw, bh)
        bg_c = (40, 40, 55)
        pygame.draw.rect(surf, bg_c, r, border_radius=5)
        pygame.draw.rect(surf, col, r, 2, border_radius=5)
        surf.blit(txt, (x + (bw - txt.get_width()) // 2, by + (bh - txt.get_height()) // 2))
        btns[bid] = r
        x += bw + 8

    # BPM
    x += 8
    lbl = font.render("BPM:", True, (170, 170, 200))
    surf.blit(lbl, (x, by + 9)); x += lbl.get_width() + 6

    r = pygame.Rect(x, by + 6, 24, 22)
    pygame.draw.rect(surf, (40, 40, 55), r, border_radius=4)
    pygame.draw.rect(surf, (120, 120, 150), r, 1, border_radius=4)
    surf.blit(font.render("-", True, (180, 180, 210)), (x + 7, by + 5))
    btns['bpm-'] = r; x += 28

    val = font.render(str(comp.bpm), True, (220, 220, 120))
    surf.blit(val, (x + 2, by + 9)); x += val.get_width() + 4

    r = pygame.Rect(x, by + 6, 24, 22)
    pygame.draw.rect(surf, (40, 40, 55), r, border_radius=4)
    pygame.draw.rect(surf, (120, 120, 150), r, 1, border_radius=4)
    surf.blit(font.render("+", True, (180, 180, 210)), (x + 7, by + 5))
    btns['bpm+'] = r; x += 38

    # Volume
    surf.blit(font.render("Vol:", True, (170, 170, 200)), (x, by + 9))
    sx = x + 40; sy = by + 8; sw = 80; sh = 18
    sr = pygame.Rect(sx, sy, sw, sh)
    pygame.draw.rect(surf, (45, 45, 58), sr, border_radius=9)
    fw = int(comp.vol * sw)
    if fw > 0:
        pygame.draw.rect(surf, (80, 170, 220), (sx, sy, fw, sh), border_radius=9)
    kx = sx + fw
    pygame.draw.circle(surf, (230, 230, 240), (kx, sy + sh // 2), 8)
    btns['volume'] = sr

    # Beat display
    pos = font.render(f"Beat {comp.playhead:.1f}", True, (130, 130, 150))
    surf.blit(pos, (W - pos.get_width() - 12, by + 9))
    return btns


def draw_grid(surf, sf, comp, gr):
    gx, gy, gw, gh = gr
    cw = gw / N_COUNT
    clip = pygame.Rect(gx, gy, gw, gh + 1)
    surf.set_clip(clip)

    pygame.draw.rect(surf, GRID_BG, (gx, gy, gw, gh))

    # Build sets for fast lookup
    live_semitones = set()
    live_octaves = set()
    for lm in comp.live_notes.keys():
        live_semitones.add(lm % 12)
        live_octaves.add(lm // 12)
    sel_sems = {LFI_DATA[p][0] for p in comp.palette_pick}

    # Black-key lanes
    for i in range(N_COUNT):
        if black(MI_LO + i):
            pygame.draw.rect(surf, (24, 26, 36), (int(gx + i * cw), gy, int(cw) + 1, gh))

    # Beat lines
    bb = comp.scroll_y / comp.beat_h
    bt = (comp.scroll_y + gh) / comp.beat_h
    for b in range(max(0, int(bb) - 1), min(TOTAL_BEATS + 1, int(bt) + 2)):
        sy = gy + gh - (b * comp.beat_h - comp.scroll_y)
        if gy <= sy <= gy + gh:
            c = (65, 70, 90) if b % 4 == 0 else (42, 45, 58)
            w = 2 if b % 4 == 0 else 1
            pygame.draw.line(surf, c, (gx, int(sy)), (gx + gw, int(sy)), w)
            if b % 4 == 0:
                lbl = sf.render(str(b), True, (90, 95, 115))
                surf.blit(lbl, (gx + 5, int(sy + 2)))

    # Pitch lines + column backgrounds
    for i in range(N_COUNT + 1):
        vx = gx + i * cw
        midi_val = MI_LO + i
        if i < N_COUNT:
            is_sel = midi_val % 12 in sel_sems
            is_live = midi_val % 12 in live_semitones
            is_live_oct = (midi_val // 12) in live_octaves
            # Column background: live highlight takes precedence over picker
            if is_live and is_live_oct:
                col = note_color(midi_val, SETTINGS["min_l"], SETTINGS["max_l"])
                bg_col = tuple(min(255, int(c * 0.25 + 55)) for c in col)
                pygame.draw.rect(surf, bg_col, (int(vx), gy, int(cw) + 1, gh))
            elif is_sel:
                col = note_color(midi_val, SETTINGS["min_l"], SETTINGS["max_l"])
                bg_col = tuple(min(255, int(c * 0.20 + 30)) for c in col)
                pygame.draw.rect(surf, bg_col, (int(vx), gy, int(cw) + 1, gh))
        c = (52, 56, 72) if i < N_COUNT and midi_val % 12 == 0 else (40, 44, 56)
        if i < N_COUNT:
            is_live_line = midi_val % 12 in live_semitones and (midi_val // 12) in live_octaves
            is_sel_line = midi_val % 12 in sel_sems
            if is_live_line:
                col = note_color(midi_val, SETTINGS["min_l"], SETTINGS["max_l"])
                c = tuple(min(255, c2 + 60) for c2 in col)
            elif is_sel_line:
                col = note_color(midi_val, SETTINGS["min_l"], SETTINGS["max_l"])
                c = tuple(min(255, c2 + 40) for c2 in col)
        pygame.draw.line(surf, c, (int(vx), gy), (int(vx), gy + gh))

    # Connecting lines (per hand group, only visible notes)
    sn = sorted(comp.visible_notes(), key=lambda x: (x.beat, x.midi))
    groups = {'left': [n for n in sn if n.hand == 'left'],
              'right': [n for n in sn if n.hand == 'right'],
              None: [n for n in sn if n.hand is None]}
    # Build index map from note object -> original index in comp.notes
    idx_map = {n: i for i, n in enumerate(comp.notes)}
    for grp in groups.values():
        if len(grp) < 2:
            continue
        for i in range(1, len(grp)):
            idx_prev = idx_map[grp[i-1]]
            idx_curr = idx_map[grp[i]]
            if not comp.is_connection_visible(idx_prev, idx_curr):
                continue
            x0, y0 = comp._n2s(grp[i-1], gr)
            x1, y1 = comp._n2s(grp[i], gr)
            next_color = grp[i].color
            # Thick solid line in next node color
            pygame.draw.line(surf, next_color, (int(x0), int(y0)), (int(x1), int(y1)), 6)

    # Nodes (only visible ones)
    RIGHT_BORDER = (255, 200, 80)
    LEFT_BORDER = (120, 180, 255)
    for n in comp.visible_notes():
        nx, ny = comp._n2s(n, gr)
        if ny < gy - 20 or ny > gy + gh + 20:
            continue
        gr2 = NR + 6
        gs = pygame.Surface((gr2*2, gr2*2), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*n.color, 45), (gr2, gr2), gr2)
        surf.blit(gs, (int(nx) - gr2, int(ny) - gr2))
        pygame.draw.circle(surf, n.color, (int(nx), int(ny)), NR)
        # Picker border (dimmed)
        if comp.palette_pick and any(n.midi % 12 == LFI_DATA[p][0] for p in comp.palette_pick):
            hl_border = tuple(min(255, c + 40) for c in n.color)
            pygame.draw.circle(surf, hl_border, (int(nx), int(ny)), NR + 2, 2)
        # Live MIDI border (brighter)
        elif n.midi in comp.live_notes:
            live_border = tuple(min(255, c + 100) for c in n.color)
            pygame.draw.circle(surf, live_border, (int(nx), int(ny)), NR + 3, 2)
        elif n.hand == 'left':
            pygame.draw.circle(surf, LEFT_BORDER, (int(nx), int(ny)), NR, 2)
        elif n.hand == 'right':
            pygame.draw.circle(surf, RIGHT_BORDER, (int(nx), int(ny)), NR, 2)
        else:
            pygame.draw.circle(surf, (230, 230, 245), (int(nx), int(ny)), NR, 1)
        hl = lerp_c(n.color, (255,255,255), 0.35)
        pygame.draw.circle(surf, hl, (int(nx) - 3, int(ny) - 3), 3)

    surf.set_clip(None)

    # Pitch labels
    for i in range(N_COUNT):
        m = MI_LO + i
        if m % 12 == 0:
            lx = gx + (i + .5) * cw
            lbl = sf.render(name(m), True, (95, 100, 120))
            surf.blit(lbl, (int(lx) - lbl.get_width()//2, gy + gh + 3))


def draw_keyboard(surf, sf, kb, active, comp):
    kx, ky, kw, kh = kb
    cw = kw / N_COUNT
    pygame.draw.rect(surf, (20, 22, 30), kb)
    pygame.draw.line(surf, (55, 55, 70), (kx, ky), (kx + kw, ky), 1)
    tck = pygame.time.get_ticks()
    SF_KEYS = "0123456789-="
    # Merge playback-active + live MIDI notes
    merged_active = set(active)
    merged_active.update(comp.live_notes.keys())
    for layer in (0, 1):
        for i in range(N_COUNT):
            m = MI_LO + i
            bl = black(m)
            if (layer == 0 and bl) or (layer == 1 and not bl):
                continue
            x = kx + i * cw; w = cw - 1
            if bl: h = kh * .55; y = ky + 3
            else: h = kh - 5; y = ky + kh - h - 2
            if m in merged_active:
                blink = (math.sin(tck * .018) + 1) / 2
                br = .45 + .55 * blink
                base = note_color(m, SETTINGS["min_l"], SETTINGS["max_l"])
                col = tuple(int(c * br) for c in base)
                pygame.draw.rect(surf, col, (int(x), int(y), int(w), int(h)), border_radius=3)
                pygame.draw.rect(surf, (240, 240, 250), (int(x), int(y), int(w), int(h)), 1, border_radius=3)
                lbl = sf.render(name(m), True, (250, 250, 250))
                surf.blit(lbl, (int(x) + max(0, (int(w) - lbl.get_width()))//2, int(y) + int(h) - lbl.get_height() - 2))
            else:
                bg = (28, 30, 42) if bl else (44, 46, 60)
                bd = (52, 54, 68) if bl else (62, 65, 80)
                pygame.draw.rect(surf, bg, (int(x), int(y), int(w), int(h)), border_radius=3)
                pygame.draw.rect(surf, bd, (int(x), int(y), int(w), int(h)), 1, border_radius=3)
                if m % 12 == 0:
                    lbl = sf.render(name(m), True, (90, 95, 115))
                    surf.blit(lbl, (int(x) + max(0, (int(w) - lbl.get_width()))//2, int(y) + int(h) - lbl.get_height() - 2))
                if not bl and not comp.palette_pick:
                    s = m % 12
                    for pos in range(12):
                        if LFI_DATA[pos][0] == s:
                            kidx = pos
                            break
                    kch = SF_KEYS[kidx] if kidx < len(SF_KEYS) else "?"
                    klbl = sf.render(kch, True, (50, 50, 65))
                    surf.blit(klbl, (int(x) + 2, int(y) + 2))

    ly0 = ky - 14
    if ly0 > TB_H:
        leg = sf.render("Palette keys: 0..9 = G0..G9  - = G10  = = G11  C = clear  M = mute", True, (60, 60, 75))
        surf.blit(leg, (4, ly0))

    return {'kb_y': ky, 'kb_h': kh, 'note_count': N_COUNT}


def draw_playline(surf, gr, kb):
    gx, gy, gw, gh = gr
    _, ky, _, _ = kb
    py = int(ky)
    for t, a in [(5, 35), (3, 80), (1, 230)]:
        ls = pygame.Surface((gw, t), pygame.SRCALPHA)
        ls.fill((255, 100, 50, a))
        surf.blit(ls, (gx, py - t // 2))
    tri = [(gx - 12, py - 10), (gx - 12, py + 10), (gx, py)]
    pygame.draw.polygon(surf, (255, 100, 50), tri)
    tri = [(gx + gw, py - 10), (gx + gw, py + 10), (gx + gw - 12, py)]
    pygame.draw.polygon(surf, (255, 100, 50), tri)


# ── main ──────────────────────────────────
def main():
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.init()
    pygame.mixer.init()
    pygame.mixer.set_num_channels(64)

    W, H = 1400, 780
    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    pygame.display.set_caption("Synesthesia Composer + Live MIDI")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 14, bold=True)
    small = pygame.font.SysFont("monospace", 11)

    comp = Comp()
    prev_sounding = set()

    # ── MIDI input setup ──
    midi_input = None
    midi_connected = False
    try:
        pygame.midi.init()
        if pygame.midi.get_count() > 0:
            dev_id = pygame.midi.get_default_input_id()
            midi_input = pygame.midi.Input(dev_id)
            dev_info = pygame.midi.get_device_info(dev_id)
            print(f"MIDI connected: {dev_info[1].decode()}")
            midi_connected = True
        else:
            print("No MIDI input devices found.")
    except Exception as e:
        print(f"MIDI init error: {e}")

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        screen.fill(BG)

        gr_x, gr_y = 0, TB_H
        gr_w, gr_h = W, H - TB_H - KB_H
        gr = (gr_x, gr_y, gr_w, gr_h)
        kb = (0, H - KB_H, gr_w, KB_H)

        btns = draw_toolbar(screen, font, comp, W)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.KEYDOWN:
                k = ev.key
                if k == pygame.K_ESCAPE: running = False
                elif k == pygame.K_SPACE: comp.playing = not comp.playing
                elif k == pygame.K_s:
                    comp.playing = False
                    comp.playhead = 0.0
                    comp.scroll_y = 0.0
                    pygame.mixer.stop()
                elif k == pygame.K_r: comp.reverse = not comp.reverse
                elif k == pygame.K_UP: comp.bpm = min(300, comp.bpm + 5)
                elif k == pygame.K_DOWN: comp.bpm = max(20, comp.bpm - 5)
                elif k == pygame.K_m: comp.muted = not comp.muted
                elif k == pygame.K_c:
                    comp.palette_pick.clear()
                elif k >= pygame.K_0 and k <= pygame.K_9:
                    idx = k - pygame.K_0
                    if idx in comp.palette_pick:
                        comp.palette_pick.discard(idx)
                    else:
                        comp.palette_pick.add(idx)
                elif k == pygame.K_MINUS:
                    if 10 in comp.palette_pick:
                        comp.palette_pick.discard(10)
                    else:
                        comp.palette_pick.add(10)
                elif k == pygame.K_EQUALS:
                    if 11 in comp.palette_pick:
                        comp.palette_pick.discard(11)
                    else:
                        comp.palette_pick.add(11)

            elif ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                mods = pygame.key.get_mods()

                if ev.button == 1:  # left
                    if comp.palette_pick:
                        # Check if clicking the palette box to clear
                        sel_sems = {LFI_DATA[p][0] for p in comp.palette_pick}
                        matching = [n for n in comp.notes if n.midi % 12 in sel_sems]
                        if matching:
                            box_w = 300; box_h = min(220, 14 + len(matching) * 16)
                            bx_c = W - box_w - 12; by_c = TB_H + 46
                            if bx_c <= mx <= bx_c + box_w and by_c <= my <= by_c + box_h:
                                comp.palette_pick.clear()
                                continue
                    if my < TB_H:
                        for bid, rect in btns.items():
                            if rect.collidepoint(mx, my):
                                if bid == 'play': comp.playing = not comp.playing
                                elif bid == 'stop':
                                    comp.playing = False; comp.playhead = 0; comp.scroll_y = 0
                                    pygame.mixer.stop()
                                elif bid == 'rev': comp.reverse = not comp.reverse
                                elif bid == 'reset': comp.playhead = 0; comp.scroll_y = 0
                                elif bid == 'clear':
                                    comp.notes.clear(); pygame.mixer.stop()
                                elif bid == 'bpm-': comp.bpm = max(20, comp.bpm - 5)
                                elif bid == 'bpm+': comp.bpm = min(300, comp.bpm + 5)
                                elif bid == 'volume':
                                    rel = max(0, min(1, (mx - rect.x) / rect.width))
                                    comp.vol = rel
                                elif bid == 'mute':
                                    comp.muted = not comp.muted
                                elif bid == 'left_toggle':
                                    if not comp.hand_visible['left']:
                                        comp.hand_visible['left'] = True
                                    elif comp.hand_muted['left']:
                                        comp.hand_muted['left'] = False
                                        comp.hand_visible['left'] = True
                                    else:
                                        comp.hand_muted['left'] = True
                                elif bid == 'right_toggle':
                                    if not comp.hand_visible['right']:
                                        comp.hand_visible['right'] = True
                                    elif comp.hand_muted['right']:
                                        comp.hand_muted['right'] = False
                                        comp.hand_visible['right'] = True
                                    else:
                                        comp.hand_muted['right'] = True
                                elif bid == 'midi':
                                    import_midi(comp)
                                break
                    elif my >= H - KB_H:
                        m = MI_LO + int((mx) / (W / N_COUNT))
                        s = m % 12
                        for pos in range(12):
                            if LFI_DATA[pos][0] == s:
                                if pos in comp.palette_pick:
                                    comp.palette_pick.discard(pos)
                                else:
                                    comp.palette_pick.add(pos)
                                break
                    elif gr_y <= my <= gr_y + gr_h:
                        if mods & pygame.KMOD_SHIFT:
                            idx = comp.note_at(mx, my, gr)
                            if idx is not None:
                                s = comp.notes[idx].midi % 12
                                for pos in range(12):
                                    if LFI_DATA[pos][0] == s:
                                        if pos in comp.palette_pick:
                                            comp.palette_pick.discard(pos)
                                        else:
                                            comp.palette_pick.add(pos)
                                        break
                        elif mods & pygame.KMOD_CTRL:
                            comp.panning = True
                            comp.pan_y = my
                        elif mods & pygame.KMOD_ALT:
                            # ALT+click on a node toggles visibility of the connection
                            # to the next node in the same hand group
                            idx = comp.note_at(mx, my, gr)
                            if idx is not None:
                                # Find next visible note in same hand group
                                target = comp.notes[idx]
                                same_hand = [i for i, n in enumerate(comp.notes)
                                             if n.hand == target.hand and comp.hand_visible.get(n.hand, True)]
                                # Find position of idx in same_hand list
                                try:
                                    pos = same_hand.index(idx)
                                except ValueError:
                                    pos = -1
                                if pos >= 0 and pos + 1 < len(same_hand):
                                    next_idx = same_hand[pos + 1]
                                    comp.toggle_connection(idx, next_idx)
                        else:
                            idx = comp.note_at(mx, my, gr)
                            if idx is not None:
                                comp.drag_idx = idx
                                nx, ny = comp._n2s(comp.notes[idx], gr)
                                comp.drag_off = (mx - nx, my - ny)
                            else:
                                m, b = comp.s2n(mx, my, gr)
                                comp.notes.append(Note(m, b))
                                if not comp.muted:
                                    mk_sound(m, .25, comp.vol).play()

                elif ev.button == 3:  # right
                    if gr_y <= my <= gr_y + gr_h:
                        idx = comp.note_at(mx, my, gr)
                        if idx is not None:
                            comp.notes.pop(idx)

            elif ev.type == pygame.MOUSEBUTTONUP:
                if ev.button == 1:
                    comp.drag_idx = None
                    comp.panning = False

            elif ev.type == pygame.MOUSEMOTION:
                mx, my = ev.pos
                if comp.panning:
                    dy = comp.pan_y - my
                    comp.scroll_y = max(0, min(comp.max_scroll(gr_h), comp.scroll_y - dy))
                    comp.pan_y = my
                elif comp.drag_idx is not None:
                    ox = mx - comp.drag_off[0]
                    oy = my - comp.drag_off[1]
                    m, b = comp.s2n(ox, oy, gr)
                    n = comp.notes[comp.drag_idx]
                    n.midi = m; n.beat = b; n.color = note_color(m, SETTINGS["min_l"], SETTINGS["max_l"])
                elif ev.buttons[0] and my < TB_H:
                    for bid, rect in btns.items():
                        if bid == 'volume' and rect.collidepoint(mx, my):
                            rel = max(0, min(1, (mx - rect.x) / rect.width))
                            comp.vol = rel

            elif ev.type == pygame.MOUSEWHEEL:
                mods = pygame.key.get_mods()
                old = comp.beat_h
                if mods & pygame.KMOD_CTRL:
                    comp.beat_h = max(12, min(120, comp.beat_h + ev.y * 4))
                else:
                    comp.scroll_y = max(0, min(comp.max_scroll(gr_h),
                                              comp.scroll_y + ev.y * comp.beat_h))
                if comp.beat_h != old:
                    ratio = comp.beat_h / old if old > 0 else 1
                    comp.scroll_y *= ratio
                    comp.scroll_y = max(0, min(comp.max_scroll(gr_h), comp.scroll_y))

            elif ev.type == pygame.VIDEORESIZE:
                W, H = ev.w, ev.h
                screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)

        # ── MIDI input processing ──
        if midi_input and midi_input.poll():
            for midi_event in midi_input.read(16):
                status, note, velocity, _ = midi_event[0]
                is_on  = (status == 144 and velocity > 0)
                is_off = (status == 128) or (status == 144 and velocity == 0)
                if is_on and MI_LO <= note <= MI_HI:
                    col = note_color(note, SETTINGS["min_l"], SETTINGS["max_l"])
                    comp.live_notes[note] = {'color': col, 'velocity': velocity}
                    if not comp.muted:
                        mk_sound(note, 0.25, comp.vol).play()
                elif is_off and note in comp.live_notes:
                    del comp.live_notes[note]

        # ── playback ──
        if comp.playing:
            bps = comp.bpm / 60
            d = -1 if comp.reverse else 1
            comp.playhead += d * bps * dt
            if comp.playhead < 0: comp.playhead = 0; comp.playing = False
            if comp.playhead >= TOTAL_BEATS: comp.playhead = 0

            target = comp.playhead * comp.beat_h
            comp.scroll_y += (target - comp.scroll_y) * 0.12
            comp.scroll_y = max(0, min(comp.max_scroll(gr_h), comp.scroll_y))

        active = set()
        if comp.playing:
            cur_idxs = comp.sounding_indices(comp.playhead)
            audible = [i for i in cur_idxs if not comp.hand_muted.get(comp.notes[i].hand, False)]
            active = {comp.notes[i].midi for i in audible}
            new_idxs = [i for i in audible if i not in prev_sounding]
            prev_sounding = set(audible)
            for i in new_idxs:
                mn = comp.notes[i].midi
                d_s = max(.08, min(1.2, .5 / bps))
                if not comp.muted:
                    mk_sound(mn, d_s, comp.vol).play()
        else:
            prev_sounding = set()

        draw_grid(screen, small, comp, gr)
        draw_playline(screen, gr, kb)
        kb_info = draw_keyboard(screen, small, kb, active, comp)

        if comp.palette_pick:
            # Build palette swatch list: one swatch per selected note class
            seq = []
            for p in sorted(comp.palette_pick):
                col = note_color(60 + p, SETTINGS["min_l"], SETTINGS["max_l"])
                seq.append((p, col))
            box_w = 320
            swatch_sz = 22
            swatch_gap = 4
            seq_h = swatch_sz + 4
            box_h = seq_h + 28
            bx = W - box_w - 12; by = TB_H + 46
            bsurf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            bsurf.fill((18, 18, 26, 230))
            screen.blit(bsurf, (bx, by))
            pygame.draw.rect(screen, (50, 50, 65), (bx, by, box_w, box_h), 1, border_radius=4)
            # Title
            names = ", ".join(LFI_DATA[p][1] for p in sorted(comp.palette_pick))
            title = small.render(f"Palette: {names}  (C = clear, click box)", True, (200, 190, 140))
            screen.blit(title, (bx + 6, by + 4))
            # Palette swatches (one per selected note class, max 12)
            sx0 = bx + 6; sy0 = by + 24
            for j, (p, col) in enumerate(seq):
                sr = pygame.Rect(sx0 + j * (swatch_sz + swatch_gap), sy0, swatch_sz, swatch_sz)
                pygame.draw.rect(screen, col, sr, border_radius=2)
                pygame.draw.rect(screen, (200, 200, 210), sr, 1, border_radius=2)
                lbl = small.render(LFI_DATA[p][1], True, (240, 240, 250))
                screen.blit(lbl, (sr.centerx - lbl.get_width()//2, sr.centery - lbl.get_height()//2))

        nc = small.render(f"{len(comp.notes)} notes", True, (100, 105, 130))
        screen.blit(nc, (W - nc.get_width() - 12, TB_H + 4))
        pygame.display.flip()

    if midi_input:
        midi_input.close()
    pygame.midi.quit()
    pygame.mixer.quit()
    pygame.quit()

if __name__ == "__main__":
    main()
