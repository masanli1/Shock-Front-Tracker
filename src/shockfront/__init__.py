"""Shock-Front Tracker: occlusion-aware tracking of explosion shock-wave fronts."""

from __future__ import annotations

from .config import TrackerConfig
from .core import process

__version__ = "1.0.0"
__all__ = ["TrackerConfig", "process", "__version__"]
