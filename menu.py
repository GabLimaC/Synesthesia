#!/usr/bin/env python3
"""
Synesthesia — Liminal Flow Intonation Suite
Launcher menu. Run with: python menu.py
"""

import sys
import os

# Add src/ to path so the synestesia package is importable without install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

APPS = [
    {
        "key": "1",
        "name": "Composer",
        "desc": "Piano-roll node-based composition tool with MIDI import/playback",
        "module": "synestesia.composer",
    },
    {
        "key": "2",
        "name": "Composer Live",
        "desc": "Composer + real-time MIDI input, hand mute/hide, connection toggling",
        "module": "synestesia.composer_live",
    },
    {
        "key": "3",
        "name": "Visualizer",
        "desc": "Real-time MIDI visualizer — Flow view + Piano Roll (Tiles / Nodes)",
        "module": "synestesia.visualizer",
    },
    {
        "key": "4",
        "name": "Visualization Page",
        "desc": "LFI Generative Circle & interactive Circle/Line Visualizer with tone playback",
        "module": "synestesia.visualization",
    },
]

_CYAN   = "\033[96m"
_YELLOW = "\033[93m"
_WHITE  = "\033[97m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"

def _color(text, code):
    """Apply ANSI color only when stdout is a tty."""
    if sys.stdout.isatty():
        return f"{code}{text}{_RESET}"
    return text

def print_menu():
    print()
    print(_color("  ╔══════════════════════════════════════════════╗", _CYAN))
    print(_color("  ║  LIMINAL FLOW INTONATION — Synesthesia Suite ║", _CYAN))
    print(_color("  ╚══════════════════════════════════════════════╝", _CYAN))
    print()
    for app in APPS:
        key  = _color(f"[{app['key']}]", _YELLOW)
        name = _color(app["name"], _BOLD)
        desc = _color(app["desc"], _DIM)
        print(f"  {key}  {name}")
        print(f"       {desc}")
        print()
    print(_color("  [q]  Quit", _DIM))
    print()

def launch(module_path):
    import importlib
    mod = importlib.import_module(module_path)
    mod.run()

def main():
    print_menu()
    while True:
        try:
            choice = input(_color("  Select > ", _CYAN)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        if choice in ("q", "quit", "exit"):
            sys.exit(0)

        match = next((a for a in APPS if a["key"] == choice), None)
        if match:
            print(_color(f"\n  Launching {match['name']}...\n", _YELLOW))
            try:
                launch(match["module"])
            except Exception as exc:
                print(_color(f"\n  Error: {exc}", "\033[91m"))
                import traceback; traceback.print_exc()
            # After the app closes, show the menu again
            print_menu()
        else:
            print(_color(f"  Unknown option '{choice}'. Enter 1, 2, 3, 4, or q.", _DIM))

if __name__ == "__main__":
    main()
