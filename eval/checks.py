"""Shim: the eval kit uses the same checks module as the service (aiscart/checks.py), so they can't drift apart."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aiscart.checks import *  # noqa: E402,F401,F403
