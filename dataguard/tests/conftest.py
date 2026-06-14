"""Pytest bootstrap: make the project root importable so ``import dataguard``
works whether pytest is invoked from the repo root or elsewhere.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
