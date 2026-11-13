"""Pip-free entry point from a source checkout."""
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "src"), str(Path(__file__).resolve().parents[1])]
from boundaryx.cli import main

raise SystemExit(main())
