#!/usr/bin/env python3
"""
Liminal Flow MIDI Visualizer — real-time MIDI input visualization.
Liminal Flow Intonation color system.

Controls:
  TAB    → toggle side menu
  V      → switch view (Flow / Piano Roll)
  ESC    → quit
"""

import pygame
import pygame.midi
import math
from ..engine import (
    LFI_DATA, get_color, lerp_c, midi_to_freq, v_hue, _hsl,
    draw_view_tabs, draw_piano_roll, draw_piano_roll_sub_tabs, draw_piano_roll_nodes,
    draw_piano_roll_relations,
    draw_flow_sub_tabs, draw_flow_relations,
    PIANO_MIDI_MIN, PIANO_MIDI_MAX, PIANO_NOTE_COUNT,
    SQUARE_ROW_H, VIEW_TAB_H, SUB_TAB_H, NODE_RADIUS, MENU_W,
    _SCALE_MODES,
)
from ..engine.core import _CLASS_TO_LINEAR_POS

# ────
# MUTABLE SETTINGS
# ────
settings = {
    "mode":            1,
    "echo_dry":        0.3,
    "trail_interval":  8.0,
    "trail_speed":     10.0,
    "palette_pick":    set(),  # canonical semitone indices (0-11)
    "chords_mode":     False,  # when True, show all held-note relationships simultaneously
    "circle_sequence": "pitch", # "pitch" = pitch space, "linear" = linear sequence (G0,G7,G2,G9,...)
    "scale_active":    False,  # toggle scale palette overlay on the note circle
    "scale_ref":       0,      # generative position of reference note (0=G0…11=G11)
    "scale_mode":      0,      # 0=Major, 1=Dorian, … 6=Locrian
    "scale_alpha":     0.0,    # animated fade for the 7-gon (target=1.0 when active, 0.0 when off)
}

# ────
# SIDE MENU
# ────
class SideMenu:
    def __init__(self, screen_h):
        self.h       = screen_h
        self.open    = True
        self.drag    = None   # 'echo_dry' | 'trail_interval' | 'trail_speed'

        self.track_x    = 20
        self.track_w    = MENU_W - 40
        self.echo_dry_y = 240
        self.interval_y = 315
        self.speed_y    = 390

    def resize(self, new_h):
        self.h = new_h

    def toggle(self):
        self.open = not self.open

    def _val_to_x(self, val, lo, hi):
        return self.track_x + int(((val - lo) / (hi - lo)) * self.track_w)

    def _x_to_val(self, x, lo, hi):
        t = max(0.0, min(1.0, (x - self.track_x) / self.track_w))
        return lo + t * (hi - lo)

    def _slider_hit(self, mx, my, cy):
        return abs(my - cy) < 14 and self.track_x - 4 <= mx <= self.track_x + self.track_w + 4

    def handle_event(self, event):
        if not self.open:
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            if mx > MENU_W:
                return
            if 100 <= my <= 130:
                settings["mode"] = 1
            elif 140 <= my <= 170:
                settings["mode"] = 2
            elif self._slider_hit(mx, my, self.echo_dry_y):
                self.drag = 'echo_dry'
                settings["echo_dry"] = round(self._x_to_val(mx, 0.05, 2.0), 2)
            elif self._slider_hit(mx, my, self.interval_y):
                self.drag = 'trail_interval'
                settings["trail_interval"] = round(self._x_to_val(mx, 1.0, 50.0))
            elif self._slider_hit(mx, my, self.speed_y):
                self.drag = 'trail_speed'
                settings["trail_speed"] = round(self._x_to_val(mx, 5.0, 300.0))

        elif event.type == pygame.MOUSEBUTTONUP:
            self.drag = None

        elif event.type == pygame.MOUSEMOTION and self.drag:
            mx = event.pos[0]
            if self.drag == 'echo_dry':
                settings["echo_dry"] = round(self._x_to_val(mx, 0.05, 2.0), 2)
            elif self.drag == 'trail_interval':
                settings["trail_interval"] = round(self._x_to_val(mx, 1.0, 50.0))
            elif self.drag == 'trail_speed':
                settings["trail_speed"] = round(self._x_to_val(mx, 5.0, 300.0))

    def draw(self, surface, fonts):
        if not self.open:
            tab = pygame.Surface((18, 80), pygame.SRCALPHA)
            tab.fill((30, 30, 30, 200))
            surface.blit(tab, (0, self.h // 2 - 40))
            arrow = fonts['xs'].render("▶", True, (180, 180, 180))
            surface.blit(arrow, (2, self.h // 2 - 8))
            return

        panel = pygame.Surface((MENU_W, self.h), pygame.SRCALPHA)
        panel.fill((18, 18, 18, 235))
        surface.blit(panel, (0, 0))
        pygame.draw.line(surface, (50, 50, 50), (MENU_W, 0), (MENU_W, self.h))

        t = fonts['sm'].render("LIMINAL FLOW", True, (200, 200, 200))
        surface.blit(t, (MENU_W // 2 - t.get_width() // 2, 18))
        t2 = fonts['xs'].render("INTONATION", True, (100, 100, 100))
        surface.blit(t2, (MENU_W // 2 - t2.get_width() // 2, 38))
        pygame.draw.line(surface, (45, 45, 45), (14, 60), (MENU_W - 14, 60))

        ml = fonts['xs'].render("MODE", True, (120, 120, 120))
        surface.blit(ml, (20, 78))

        for idx, (label, desc) in enumerate([
            ("1 — Relative", "C = G0 = Blue"),
            ("2 — Absolute", "40 Hz root"),
        ]):
            by = 100 + idx * 40
            active    = (settings["mode"] == idx + 1)
            btn_color = (40, 80, 140) if active else (35, 35, 35)
            border    = (80, 140, 220) if active else (55, 55, 55)
            pygame.draw.rect(surface, btn_color, (14, by, MENU_W - 28, 28), border_radius=5)
            pygame.draw.rect(surface, border,    (14, by, MENU_W - 28, 28), 1, border_radius=5)
            lt = fonts['xs'].render(label, True, (230, 230, 230) if active else (140, 140, 140))
            dt = fonts['xs'].render(desc,  True, (160, 200, 255) if active else (80, 80, 80))
            surface.blit(lt, (22, by + 4))
            surface.blit(dt, (MENU_W - dt.get_width() - 16, by + 4))

        pygame.draw.line(surface, (45, 45, 45), (14, 185), (MENU_W - 14, 185))

        el = fonts['xs'].render("ECHO TAIL", True, (120, 120, 120))
        surface.blit(el, (20, 198))
        self._draw_slider(surface, fonts, "Dry (no pedal)",
                    settings["echo_dry"], self.echo_dry_y, (180, 140, 80), 0.05, 2.0,
                    fmt=f"{settings['echo_dry']:.2f}s")

        pygame.draw.line(surface, (45, 45, 45), (14, 278), (MENU_W - 14, 278))

        tl = fonts['xs'].render("PIANO ROLL TRAIL", True, (120, 120, 120))
        surface.blit(tl, (20, 290))
        self._draw_slider(surface, fonts, "Trail segments",
                    settings["trail_interval"], self.interval_y, (160, 140, 220), 1.0, 50.0,
                    fmt=f"{int(settings['trail_interval'])}")
        self._draw_slider(surface, fonts, "Rise speed",
                    settings["trail_speed"], self.speed_y, (140, 200, 160), 5.0, 300.0,
                    fmt=f"{int(settings['trail_speed'])}")

        hint = fonts['xs'].render("[TAB] collapse", True, (60, 60, 60))
        surface.blit(hint, (MENU_W // 2 - hint.get_width() // 2, self.h - 28))

    def _draw_slider(self, surface, fonts, label, value, cy, knob_color, lo=0, hi=100, fmt=None):
        display = fmt if fmt else f"{value:.0f}%"
        lbl = fonts['xs'].render(f"{label}:  {display}", True, (160, 160, 160))
        surface.blit(lbl, (self.track_x, cy - 22))
        pygame.draw.rect(surface, (50, 50, 50),
                    (self.track_x, cy - 3, self.track_w, 6), border_radius=3)
        fill_w = int(((value - lo) / (hi - lo)) * self.track_w)
        fill_w = max(0, min(self.track_w, fill_w))
        pygame.draw.rect(surface, knob_color,
                    (self.track_x, cy - 3, fill_w, 6), border_radius=3)
        kx = self.track_x + fill_w
        pygame.draw.circle(surface, (230, 230, 255), (kx, cy), 9)
        pygame.draw.circle(surface, knob_color,      (kx, cy), 7)


# ────
# MAIN
# ────
def main():
    pygame.init()
    pygame.midi.init()

    if pygame.midi.get_count() == 0:
        print("No MIDI devices found.")
        return

    dev_id     = pygame.midi.get_default_input_id()
    midi_input = pygame.midi.Input(dev_id)
    dev_info   = pygame.midi.get_device_info(dev_id)
    print(f"Connected: {dev_info[1].decode()}")

    W, H = 1000, 620
    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    pygame.display.set_caption("Liminal Flow — MIDI Visualizer")
    clock = pygame.time.Clock()

    fonts = {
        'xl': pygame.font.SysFont("monospace", 96, bold=True),
        'lg': pygame.font.SysFont("monospace", 36, bold=True),
        'sm': pygame.font.SysFont("monospace", 16, bold=True),
        'xs': pygame.font.SysFont("monospace", 13),
    }

    menu = SideMenu(H)
    BG   = (8, 8, 8)

    FADE_IN_SPEED  = 0.18          # ~6 frames to full brightness
    FPS            = 60.0

    # note_states: midi_note (int) → dict (see above)
    note_states: dict = {}

    view_tab = 0
    piano_roll_sub = 0   # 0 = tiles, 1 = nodes

    # Trail columns for Piano Roll tiles view
    trail_columns: list = []

    # Node trail for Piano Roll nodes view
    # Each node: { 'midi_note': int, 'cx': float, 'cy': float, 'color': tuple }
    node_trail: list = []

    # Relation pair tracking for the Relations sub-view
    # { 'left': (class, midi, color, label, v) | None, 'right': ditto | None }
    relation_pair = None

    # Flow sub-tab and relation color state
    flow_sub = 0        # 0 = note color, 1 = relation color
    flow_rel_state = {'ref': None, 'target': None, 'step': 0, 'sign': '', 'fade_alpha': 0.0}

    print("TAB = menu  |  V = view  |  K = chords  |  S = circle seq  |  L = scale  |  [/] = mode  |  ESC = quit")

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_TAB:
                    menu.toggle()
                elif event.key == pygame.K_v:
                    view_tab = 1 - view_tab
                    trail_columns.clear()
                    node_trail.clear()
                elif event.key == pygame.K_k:
                    settings["chords_mode"] = not settings["chords_mode"]
                elif event.key == pygame.K_b:
                    if view_tab == 0:
                        flow_sub = 1 - flow_sub
                elif event.key == pygame.K_s:
                    cur = settings.get("circle_sequence", "pitch")
                    settings["circle_sequence"] = "linear" if cur == "pitch" else "pitch"
                elif event.key == pygame.K_l:
                    settings["scale_active"] = not settings["scale_active"]
                elif event.key == pygame.K_LEFTBRACKET:
                    settings["scale_mode"] = (settings["scale_mode"] - 1) % 7
                elif event.key == pygame.K_RIGHTBRACKET:
                    settings["scale_mode"] = (settings["scale_mode"] + 1) % 7
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                cx0 = MENU_W if menu.open else 0
                cw0 = W - cx0
                # Click on view tab bar
                if my < VIEW_TAB_H and mx >= cx0:
                    rel = mx - cx0
                    view_tab = 0 if rel < cw0 // 2 else 1
                    trail_columns.clear()
                    node_trail.clear()
                # Click on flow sub-tab bar
                elif view_tab == 0 and VIEW_TAB_H <= my < VIEW_TAB_H + SUB_TAB_H and mx >= cx0:
                    rel = mx - cx0
                    flow_sub = int(rel / (cw0 / 2))
                # Click on piano-roll sub-tab bar
                elif view_tab == 1 and VIEW_TAB_H <= my < VIEW_TAB_H + SUB_TAB_H and mx >= cx0:
                    rel = mx - cx0
                    piano_roll_sub = int(rel / (cw0 / 3))
                    trail_columns.clear()
                    node_trail.clear()
                # Click on piano-roll note squares (palette pick)
                elif view_tab == 1 and my >= H - SQUARE_ROW_H and mx >= cx0:
                    rel = mx - cx0
                    sq_idx = int(rel / (cw0 / PIANO_NOTE_COUNT))
                    if 0 <= sq_idx < PIANO_NOTE_COUNT:
                        midi_note = PIANO_MIDI_MIN + sq_idx
                        semitone = (midi_note - 60) % 12
                        pick = settings["palette_pick"]
                        if semitone in pick:
                            pick.discard(semitone)
                        else:
                            pick.add(semitone)
                # Click on relations view controls (toggles, swipe, palette)
                elif view_tab == 1 and piano_roll_sub == 2 and mx >= cx0:
                    from ..engine.core import draw_piano_roll_relations as _rfn
                    from ..engine.core import _swipe_state, _SCALE_MODES
                    cr = getattr(_rfn, '_ctrl_rects', None)
                    STEP_PX = 30
                    if cr:
                        for key, (rx, ry, rw, rh) in cr.items():
                            if rx <= mx <= rx + rw and ry <= my <= ry + rh:
                                if key == 'chords':
                                    settings["chords_mode"] = not settings["chords_mode"]
                                elif key == 'scale':
                                    settings["scale_active"] = not settings["scale_active"]
                                elif key == 'seq':
                                    cur = settings.get("circle_sequence", "pitch")
                                    settings["circle_sequence"] = "linear" if cur == "pitch" else "pitch"
                                elif key == 'pal_clear':
                                    settings["palette_pick"].clear()
                                elif key == 'ref':
                                    _swipe_state['drag'] = 'ref'
                                    _swipe_state['start_mx'] = mx
                                    _swipe_state['start_val'] = settings.get("scale_ref", 0)
                                    _swipe_state['accum'] = 0.0
                                elif key == 'mode':
                                    _swipe_state['drag'] = 'mode'
                                    _swipe_state['start_mx'] = mx
                                    _swipe_state['start_val'] = settings.get("scale_mode", 0)
                                    _swipe_state['accum'] = 0.0
                                break
            elif event.type == pygame.VIDEORESIZE:
                W, H = event.w, event.h
                screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
                menu.resize(H)
            menu.handle_event(event)
            # swipe drag for relations view controls
            if view_tab == 1 and piano_roll_sub == 2:
                from ..engine.core import _swipe_state
                if event.type == pygame.MOUSEMOTION and _swipe_state['drag'] is not None:
                    mx = event.pos[0]
                    delta = mx - _swipe_state['start_mx']
                    _swipe_state['accum'] = delta
                    STEP_PX = 30
                    if _swipe_state['drag'] == 'ref':
                        raw = _swipe_state['start_val'] - round(delta / STEP_PX)
                        settings["scale_ref"] = max(0, min(11, raw))
                    elif _swipe_state['drag'] == 'mode':
                        raw = _swipe_state['start_val'] - round(delta / STEP_PX)
                        settings["scale_mode"] = raw % 7
                elif event.type == pygame.MOUSEBUTTONUP:
                    _swipe_state['drag'] = None
                    _swipe_state['accum'] = 0.0

        # ── MIDI Input ────
        if midi_input.poll():
            for midi_event in midi_input.read(16):
                status, note, velocity, _ = midi_event[0]
                is_on  = (status == 144 and velocity > 0)
                is_off = (status == 128) or (status == 144 and velocity == 0)

                if is_on:
                    color, label, v, _ = get_color(note, velocity, settings["mode"], 50, 50)
                    semitone = (note - 60) % 12
                    # LFI_DATA is in LINEAR (frequency) order; index = chromatic semitone
                    g_class = LFI_DATA[semitone][0]
                    # ── relation pair tracking ──
                    entry = (g_class, note, color, label, v)
                    if relation_pair is None:
                        relation_pair = {'left': entry, 'right': None}
                    else:
                        if relation_pair['right'] is not None:
                            relation_pair['left'] = relation_pair['right']
                        relation_pair['right'] = entry
                    # ── note_states ──
                    if note in note_states:
                        note_states[note].update(
                            color=color, label=label, v=v, semitone=semitone,
                            vel=velocity, held=True, echo_timer=None,
                        )
                    else:
                        note_states[note] = dict(
                            color=color, disp_color=BG,
                            label=label, v=v, semitone=semitone, vel=velocity,
                            alpha=0.0, held=True, echo_timer=None,
                        )

                    # ── flow relations tracking ──
                    if view_tab == 0 and flow_sub == 1:
                        cp = _CLASS_TO_LINEAR_POS[g_class]
                        new_entry = (g_class, note, color, label, cp)
                        if flow_rel_state['ref'] is None:
                            flow_rel_state['ref'] = new_entry
                            flow_rel_state['target'] = None
                            flow_rel_state['step'] = 0
                            flow_rel_state['sign'] = ''
                            flow_rel_state['fade_alpha'] = 0.0
                        elif g_class == flow_rel_state['ref'][0]:
                            flow_rel_state['target'] = None
                            flow_rel_state['step'] = 0
                            flow_rel_state['sign'] = ''
                            flow_rel_state['fade_alpha'] = 0.0
                        else:
                            # ref = prev note, target = latest note
                            if flow_rel_state['target'] is not None:
                                flow_rel_state['ref'] = flow_rel_state['target']
                            flow_rel_state['target'] = new_entry
                            rg = flow_rel_state['ref'][0]
                            tg = flow_rel_state['target'][0]
                            gen_dist = (tg - rg) % 12
                            if gen_dist == 0:
                                flow_rel_state['step'] = 0
                                flow_rel_state['sign'] = ''
                            elif gen_dist == 6:
                                flow_rel_state['step'] = 6
                                flow_rel_state['sign'] = '-R'
                            elif gen_dist < 6:
                                flow_rel_state['step'] = gen_dist
                                flow_rel_state['sign'] = '+'
                            else:
                                flow_rel_state['step'] = 12 - gen_dist
                                flow_rel_state['sign'] = '-'
                            flow_rel_state['fade_alpha'] = 0.0

                    if view_tab == 1 and piano_roll_sub == 1:
                        if PIANO_MIDI_MIN <= note <= PIANO_MIDI_MAX:
                            cx_now = MENU_W if menu.open else 0
                            cw_now = W - cx_now
                            sq_w_n = cw_now / PIANO_NOTE_COUNT
                            sq_idx = note - PIANO_MIDI_MIN
                            ncx    = cx_now + sq_idx * sq_w_n + sq_w_n / 2
                            ncy    = float(H - SQUARE_ROW_H - NODE_RADIUS - 2)
                            node_trail.append({
                                'midi_note': note, 'cx': ncx, 'cy': ncy,
                                'color': color,
                            })

                elif is_off and note in note_states:
                    note_states[note]['held'] = False
                    if note_states[note].get('echo_timer') is None:
                        note_states[note]['echo_timer'] = settings["echo_dry"]

        # ── Per-note alpha update ────
        decay_time = settings["echo_dry"]
        fade_out_speed = 1.0 / (decay_time * FPS)

        to_remove = []
        for note, ns in note_states.items():
            if ns['held']:
                ns['alpha'] = min(1.0, ns['alpha'] + FADE_IN_SPEED)
                ns['echo_timer'] = None  # while held, no countdown yet
            elif ns['echo_timer'] is not None:
                ns['echo_timer'] -= 1 / FPS
                if ns['echo_timer'] <= 0:
                    to_remove.append(note)
                else:
                    ns['alpha'] = max(0.0, ns['alpha'] - fade_out_speed)
            else:
                # released with no echo_timer → start countdown
                ns['echo_timer'] = decay_time
        for note in to_remove:
            del note_states[note]

        # ── Piano Roll: update trail columns ────
        if view_tab == 1:
            content_x_now = MENU_W if menu.open else 0
            content_w_now = W - content_x_now
            trail_area_h  = max(1, H - SQUARE_ROW_H - VIEW_TAB_H)
            sq_w_now      = content_w_now / PIANO_NOTE_COUNT

            speed = settings["trail_speed"]

            # ALL trail columns scroll upward every frame (the roll)
            for col in trail_columns:
                col['y'] -= speed / FPS

            # Held notes: grow column upward from the bottom
            for midi_note, ns in note_states.items():
                if not (PIANO_MIDI_MIN <= midi_note <= PIANO_MIDI_MAX):
                    continue

                sq_idx = midi_note - PIANO_MIDI_MIN
                px     = content_x_now + sq_idx * sq_w_now
                pw     = sq_w_now

                if ns['held']:
                    trail_columns.append({
                    'x': px, 'w': pw, 'y': H - SQUARE_ROW_H, 'h': 2,
                    'color': ns['color'], 'midi_note': midi_note,
                    })

            # Remove columns that scrolled fully off the screen
            trail_columns = [c for c in trail_columns if c['y'] + c['h'] > 0]

            # Scroll nodes upward and cull off-screen
            for node in node_trail:
                node['cy'] -= speed / FPS
            node_trail_top = VIEW_TAB_H + SUB_TAB_H
            node_trail = [n for n in node_trail if n['cy'] + NODE_RADIUS > node_trail_top]

        # ── Scale palette alpha animation ──
        target_alpha = 1.0 if settings.get("scale_active", False) else 0.0
        current_alpha = settings.get("scale_alpha", 0.0)
        if current_alpha < target_alpha:
            current_alpha = min(target_alpha, current_alpha + 0.08)
        elif current_alpha > target_alpha:
            current_alpha = max(target_alpha, current_alpha - 0.08)
        settings["scale_alpha"] = current_alpha

        # ── Flow relations fade animation ──
        flow_rel_state['fade_alpha'] = min(1.0, flow_rel_state['fade_alpha'] + 0.08)

        # ── Determine content area ────
        content_x = MENU_W if menu.open else 0
        content_w = W - content_x

        # ── Render ────
        screen.fill(BG)

        if view_tab == 0:
            # ── VIEW 0: original Flow view ──
            if flow_sub == 0:
                if note_states:
                    sorted_notes = sorted(note_states.keys())   # low → high pitch
                    n_notes  = len(sorted_notes)
                    panel_w  = content_w // n_notes

                    for i, midi_note in enumerate(sorted_notes):
                        ns    = note_states[midi_note]
                        alpha = ns['alpha']

                        # Lerp displayed color toward target (smooth chord transitions)
                        ns['disp_color'] = lerp_c(ns['disp_color'], ns['color'], 0.25)

                        # Apply per-note alpha: fade from BG to disp_color
                        faded_color = lerp_c(BG, ns['disp_color'], alpha)

                        px = content_x + i * panel_w
                        pw = panel_w if i < n_notes - 1 else content_w - (n_notes - 1) * panel_w

                        # Panel background (leave room for tab bar and sub-tabs at top)
                        content_top = VIEW_TAB_H + SUB_TAB_H
                        pygame.draw.rect(screen, faded_color, (px, content_top, pw, H - content_top))

                        # Palette pick highlight border
                        palette_pick = settings.get("palette_pick")
                        if palette_pick and ns.get('semitone') in palette_pick:
                            pygame.draw.rect(screen, (255, 200, 60), (px, content_top, pw, H - content_top), 3)

                        # Divider
                        if i > 0:
                            div_color = tuple(max(0, c - 30) for c in faded_color)
                            pygame.draw.line(screen, div_color, (px, content_top), (px, H), 2)

                        # Note label
                        cx_panel = px + pw // 2
                        if pw >= 200:
                            label_font = fonts['xl']
                            info_font  = fonts['xs']
                        elif pw >= 100:
                            label_font = fonts['lg']
                            info_font  = fonts['xs']
                        else:
                            label_font = fonts['sm']
                            info_font  = None

                        txt_v     = int(alpha * 255)
                        txt_color = (txt_v, txt_v, txt_v)

                        big = label_font.render(ns['label'], True, txt_color)
                        screen.blit(big, (cx_panel - big.get_width() // 2,
                            content_top + (H - content_top) // 2 - big.get_height() // 2))

                        if info_font and pw >= 140:
                            freq     = midi_to_freq(midi_note)
                            info_str = f"{freq:.1f}Hz  v={ns['v']:.3f}  vel={ns['vel']}"
                            info_s   = info_font.render(info_str, True, txt_color)

                            strip = pygame.Surface((pw, 28), pygame.SRCALPHA)
                            strip.fill((0, 0, 0, int(alpha * 140)))
                            screen.blit(strip, (px, H - 30))
                            screen.blit(info_s, (cx_panel - info_s.get_width() // 2, H - 24))

                else:
                    content_top = VIEW_TAB_H + SUB_TAB_H
                    cx   = content_x + content_w // 2
                    idle = fonts['sm'].render("play a note...", True, (50, 50, 50))
                    screen.blit(idle, (cx - idle.get_width() // 2,
                        content_top + (H - content_top) // 2 - 10))
            else:
                draw_flow_relations(screen, fonts, flow_rel_state, note_states,
                    content_x, content_w, W, H, BG)
            draw_flow_sub_tabs(screen, fonts, content_x, content_w, flow_sub)

        else:
            # ── VIEW 1: Piano Roll view ────
            if piano_roll_sub == 0:
                draw_piano_roll(screen, fonts, note_states, trail_columns,
                    content_x, content_w, W, H, BG,
                    palette_pick=settings.get("palette_pick"))
            elif piano_roll_sub == 1:
                draw_piano_roll_nodes(screen, fonts, note_states, node_trail,
                    content_x, content_w, W, H, BG,
                    palette_pick=settings.get("palette_pick"))
            else:
                draw_piano_roll_relations(screen, fonts, note_states, relation_pair,
                    content_x, content_w, W, H, BG,
                    chords_mode=settings.get("chords_mode", False),
                    circle_sequence=settings.get("circle_sequence", "pitch"),
                    scale_ref=settings.get("scale_ref", 0),
                    scale_mode=settings.get("scale_mode", 0),
                    scale_active=settings.get("scale_active", False),
                    scale_alpha=settings.get("scale_alpha", 0.0),
                    palette_pick=settings.get("palette_pick"))
            # Sub-tab bar (drawn on top of trail area)
            draw_piano_roll_sub_tabs(screen, fonts, content_x, content_w, piano_roll_sub)

        # ── View tab bar (drawn on top, above content) ────
        draw_view_tabs(screen, fonts, content_x, content_w, view_tab)

        menu.draw(screen, fonts)
        pygame.display.flip()
        clock.tick(FPS)

    midi_input.close()
    pygame.midi.quit()
    pygame.quit()

if __name__ == "__main__":
    main()
