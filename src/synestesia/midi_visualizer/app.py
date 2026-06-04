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
    PIANO_MIDI_MIN, PIANO_MIDI_MAX, PIANO_NOTE_COUNT,
    SQUARE_ROW_H, VIEW_TAB_H, SUB_TAB_H, NODE_RADIUS, MENU_W,
)

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
        self.echo_dry_y = 435
        self.interval_y = 525
        self.speed_y    = 605

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
            elif 218 <= my <= 246:
                settings["chords_mode"] = not settings.get("chords_mode", False)
            elif 290 <= my <= 318:
                cur = settings.get("circle_sequence", "pitch")
                settings["circle_sequence"] = "linear" if cur == "pitch" else "pitch"
            elif 355 <= my <= 385 and settings.get("palette_pick") and mx > MENU_W - 60:
                settings["palette_pick"].clear()
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

        # Chords mode toggle
        cl = fonts['xs'].render("CHORDS MODE", True, (120, 120, 120))
        surface.blit(cl, (20, 198))
        chords_active = settings.get("chords_mode", False)
        btn_color = (40, 80, 140) if chords_active else (35, 35, 35)
        border = (80, 140, 220) if chords_active else (55, 55, 55)
        pygame.draw.rect(surface, btn_color, (14, 218, MENU_W - 28, 28), border_radius=5)
        pygame.draw.rect(surface, border, (14, 218, MENU_W - 28, 28), 1, border_radius=5)
        ct = fonts['xs'].render("K — ON" if chords_active else "K — OFF", True,
                               (230, 230, 230) if chords_active else (80, 80, 80))
        surface.blit(ct, (22, 222))
        hint_k = fonts['xs'].render("relations view", True, (70, 70, 70) if not chords_active else (160, 200, 255))
        surface.blit(hint_k, (MENU_W - hint_k.get_width() - 16, 224))

        # Circle sequence toggle
        sl = fonts['xs'].render("CIRCLE SEQUENCE", True, (120, 120, 120))
        surface.blit(sl, (20, 270))
        seq = settings.get("circle_sequence", "pitch")
        seq_lin = (seq == "linear")
        btn_c = (40, 80, 140) if seq_lin else (35, 35, 35)
        bdr_c = (80, 140, 220) if seq_lin else (55, 55, 55)
        pygame.draw.rect(surface, btn_c, (14, 290, MENU_W - 28, 28), border_radius=5)
        pygame.draw.rect(surface, bdr_c, (14, 290, MENU_W - 28, 28), 1, border_radius=5)
        lb = fonts['xs'].render("Pitch Space" if not seq_lin else "Linear", True,
                               (230, 230, 230) if seq_lin else (200, 200, 200))
        surface.blit(lb, (22, 294))
        hk = fonts['xs'].render("S", True, (70, 70, 70) if not seq_lin else (160, 200, 255))
        surface.blit(hk, (MENU_W - hk.get_width() - 16, 296))

        pygame.draw.line(surface, (45, 45, 45), (14, 330), (MENU_W - 14, 330))

        pl = fonts['xs'].render("PALETTE PICK", True, (120, 120, 120))
        surface.blit(pl, (20, 345))
        pp = settings.get("palette_pick")
        if pp:
            pp_canonical = [LFI_DATA[p] for p in sorted(pp)]
            swatch_w = 18; swatch_h = 18; swatch_gap = 4
            for idx, entry in enumerate(pp_canonical):
                p = entry[0]
                entry_v = entry[3]
                pp_color = _hsl(v_hue(entry_v), 100, 50)
                swatch_x = 14 + idx * (swatch_w + swatch_gap)
                pygame.draw.rect(surface, pp_color, (swatch_x, 363, swatch_w, swatch_h), border_radius=3)
                pygame.draw.rect(surface, (200, 200, 200), (swatch_x, 363, swatch_w, swatch_h), 1, border_radius=3)
            # Label line
            names = ", ".join(entry[1] for entry in pp_canonical)
            pp_label = fonts['xs'].render(f"Semitones {names}", True, (180, 180, 180))
            surface.blit(pp_label, (14, 387))
            clear_btn = fonts['xs'].render("clear", True, (140, 100, 100))
            surface.blit(clear_btn, (MENU_W - clear_btn.get_width() - 16, 365))
        else:
            hint_p = fonts['xs'].render("click piano-roll note", True, (70, 70, 70))
            surface.blit(hint_p, (20, 367))

        pygame.draw.line(surface, (45, 45, 45), (14, 393), (MENU_W - 14, 393))

        el = fonts['xs'].render("ECHO TAIL", True, (120, 120, 120))
        surface.blit(el, (20, 407))
        self._draw_slider(surface, fonts, "Dry (no pedal)",
                    settings["echo_dry"], self.echo_dry_y, (180, 140, 80), 0.05, 2.0,
                    fmt=f"{settings['echo_dry']:.2f}s")

        pygame.draw.line(surface, (45, 45, 45), (14, 480), (MENU_W - 14, 480))

        tl = fonts['xs'].render("PIANO ROLL TRAIL", True, (120, 120, 120))
        surface.blit(tl, (20, 497))
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

    print("TAB = toggle menu  |  V = switch view  |  K = chords  |  S = circle seq  |  ESC = quit")

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
                elif event.key == pygame.K_s:
                    cur = settings.get("circle_sequence", "pitch")
                    settings["circle_sequence"] = "linear" if cur == "pitch" else "pitch"
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
            elif event.type == pygame.VIDEORESIZE:
                W, H = event.w, event.h
                screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
                menu.resize(H)
            menu.handle_event(event)

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

        # ── Determine content area ────
        content_x = MENU_W if menu.open else 0
        content_w = W - content_x

        # ── Render ────
        screen.fill(BG)

        if view_tab == 0:
            # ── VIEW 0: original Flow view ────
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

                    # Panel background (leave room for tab bar at top)
                    pygame.draw.rect(screen, faded_color, (px, VIEW_TAB_H, pw, H - VIEW_TAB_H))

                    # Palette pick highlight border
                    palette_pick = settings.get("palette_pick")
                    if palette_pick and ns.get('semitone') in palette_pick:
                        pygame.draw.rect(screen, (255, 200, 60), (px, VIEW_TAB_H, pw, H - VIEW_TAB_H), 3)

                    # Divider
                    if i > 0:
                        div_color = tuple(max(0, c - 30) for c in faded_color)
                        pygame.draw.line(screen, div_color, (px, VIEW_TAB_H), (px, H), 2)

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
                        VIEW_TAB_H + (H - VIEW_TAB_H) // 2 - big.get_height() // 2))

                    if info_font and pw >= 140:
                        freq     = midi_to_freq(midi_note)
                        info_str = f"{freq:.1f}Hz  v={ns['v']:.3f}  vel={ns['vel']}"
                        info_s   = info_font.render(info_str, True, txt_color)

                        strip = pygame.Surface((pw, 28), pygame.SRCALPHA)
                        strip.fill((0, 0, 0, int(alpha * 140)))
                        screen.blit(strip, (px, H - 30))
                        screen.blit(info_s, (cx_panel - info_s.get_width() // 2, H - 24))

            else:
                cx   = content_x + content_w // 2
                idle = fonts['sm'].render("play a note...", True, (50, 50, 50))
                screen.blit(idle, (cx - idle.get_width() // 2,
                    VIEW_TAB_H + (H - VIEW_TAB_H) // 2 - 10))

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
                    circle_sequence=settings.get("circle_sequence", "pitch"))
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
