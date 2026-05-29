"""Entry-point: python -m synestesia  (or via the 'synestesia' console script)."""
import sys
import os

# When run as a module inside the installed package, menu.py lives at the
# project root (one level above src/). Make it importable.
_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import importlib.util
_menu_path = os.path.join(_root, "menu.py")
_spec = importlib.util.spec_from_file_location("_synestesia_menu", _menu_path)
_menu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_menu)

def main():
    _menu.main()

if __name__ == "__main__":
    main()
