#!/usr/bin/env python3
"""Generate a synthetic sequence, run the tracker, and refresh docs assets."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_synthetic import make_sequence           # noqa: E402
from shockfront import TrackerConfig, process      # noqa: E402


def main() -> None:
    assets = ROOT / "docs" / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="shockfront-demo-") as tmp:
        tmp = Path(tmp)
        frames = tmp / "frames"
        results = tmp / "results"
        make_sequence(frames, n_frames=16)

        cfg = TrackerConfig(
            fps=1000.0,
            bright_threshold=100.0,
            sal_threshold=5.0,
            min_measured_rows=40,
            fit_tolerance=10.0,
            measure_tolerance=10.0,
            shape_jump_tol=12.0,
            cross_band=None,
            bar_clearance=15.0,
        )
        process(frames, results, cfg)

        shutil.copyfile(results / "preview.gif", assets / "demo.gif")
        shutil.copyfile(results / "contact_sheet.png", assets / "demo_contact_sheet.png")
        shutil.copyfile(results / "curves.png", assets / "demo_curves.png")
    print(f"updated {assets / 'demo.gif'} and {assets / 'demo_contact_sheet.png'}")


if __name__ == "__main__":
    main()
