"""LFI Engine — color system, audio synthesis, MIDI import, drawing helpers."""
from .core import (
    # color system
    F_BASE, F_TOP, TOTAL_OCTAVES, LFI_DATA, SEM,
    _hsl, v_hue, note_color, liminal_color,
    velocity_to_saturation, get_color_relative, get_color_absolute, get_color,
    lerp_c,
    # MIDI / frequency helpers
    midi_to_freq, m2f, name, black,
    MIDO_AVAILABLE,
    # audio
    SR, mk_sound,
    # tkinter helper
    _tk_root,
    # data class
    Note,
    # MIDI import
    import_midi,
    # shared constants
    MI_LO, MI_HI, N_COUNT, TOTAL_BEATS, DEF_BPM,
    NR, NGR, KB_H, TB_H, BG, GRID_BG,
    PIANO_MIDI_MIN, PIANO_MIDI_MAX, PIANO_NOTE_COUNT,
    SQUARE_ROW_H, VIEW_TAB_H, SUB_TAB_H, NODE_RADIUS, MENU_W,
    # drawing helpers
    draw_rounded, draw_view_tabs, draw_piano_roll,
    draw_piano_roll_sub_tabs, draw_piano_roll_nodes,
    draw_piano_roll_relations,
)
