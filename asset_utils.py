"""Helper for locating asset files both in source and PyInstaller bundles."""

import os
import sys
from pathlib import Path


def asset_path(relative_path: str) -> str:
    """
    Resolve an asset path that works in development and in PyInstaller bundles.

    Args:
        relative_path: Path relative to the project root (e.g., "Assets/Player/hero.png").

    Returns:
        Absolute path to the asset inside the source tree or the PyInstaller temp dir.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    rel = Path(relative_path)
    if rel.is_absolute():
        return str(rel)
    return str(base / rel)
