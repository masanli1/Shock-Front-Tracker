#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command-line interface for the shock-front tracker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .config import TrackerConfig
from .core import process


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shockfront",
        description="Track the outermost shock-wave front in high-speed image sequences.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    track = sub.add_parser(
        "track",
        help="run the full tracking pipeline",
        description="Run the full shock-front tracking pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    track.add_argument("--input", "-i", required=True, help="input image folder")
    track.add_argument("--output", "-o", default="results", help="output folder")
    track.add_argument("--fps", type=float, default=75000.0, help="frame rate")
    track.add_argument("--roi-top", type=int, default=None,
                       help="header height in pixels; auto-detect by default")
    track.add_argument("--hp-sigma", type=float, default=6.0,
                       help="high-pass sigma (pixels)")
    track.add_argument("--static-percentile", type=float, default=20.0,
                       help="percentile for the static response map")
    track.add_argument("--bright-threshold", type=float, default=80.0,
                       help="brightness threshold for early thin edges")
    track.add_argument("--sal-threshold", type=float, default=8.0,
                       help="saliency threshold for moving arcs")
    track.add_argument("--bar-pad", type=int, default=4,
                       help="pixels to pad around detected bars")
    track.add_argument("--bar-clearance", type=float, default=20.0,
                       help="freeze shape when the front is this close to a bar")
    track.add_argument("--median-window", type=int, default=21)
    track.add_argument("--max-deviation", type=float, default=14.0)
    track.add_argument("--max-gap", type=int, default=24)
    track.add_argument("--smooth-window", type=int, default=7)
    track.add_argument("--min-measured-rows", type=int, default=80)
    track.add_argument("--fit-tolerance", type=float, default=12.0)
    track.add_argument("--measure-tolerance", type=float, default=12.0)
    track.add_argument("--inertia-alpha", type=float, default=0.2,
                       help="shape update gain away from occlusions")
    track.add_argument("--shape-jump-tol", type=float, default=8.0)
    track.add_argument("--shape-smooth-y", type=int, default=9)
    track.add_argument("--no-gif", action="store_true")
    track.add_argument("--no-contact-sheet", action="store_true")
    track.add_argument("--no-plot", action="store_true")
    track.add_argument("--gif-every", type=int, default=2)
    track.add_argument("--limit", type=int, default=0)
    track.add_argument("--quiet", "-q", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Allow both `shockfront track ...` and `shockfront --input ...`.
    if not argv or argv[0] not in {"track", "--help", "-h", "--version", "-V"}:
        argv = ["track"] + argv

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "track":
        parser.print_help()
        return 0

    cfg = TrackerConfig(
        roi_top=args.roi_top,
        hp_sigma=args.hp_sigma,
        static_percentile=args.static_percentile,
        bright_threshold=args.bright_threshold,
        sal_threshold=args.sal_threshold,
        bar_pad=args.bar_pad,
        bar_clearance=args.bar_clearance,
        median_window=args.median_window,
        max_deviation=args.max_deviation,
        max_gap=args.max_gap,
        smooth_window=args.smooth_window,
        min_measured_rows=args.min_measured_rows,
        fit_tolerance=args.fit_tolerance,
        measure_tolerance=args.measure_tolerance,
        inertia_alpha=args.inertia_alpha,
        shape_jump_tol=args.shape_jump_tol,
        shape_smooth_y=args.shape_smooth_y,
        fps=args.fps,
        make_gif=not args.no_gif,
        gif_every=args.gif_every,
        make_contact_sheet=not args.no_contact_sheet,
        make_plot=not args.no_plot,
        limit=args.limit,
    )

    input_dir = Path(args.input).expanduser().resolve()
    out_dir = Path(args.output).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"error: input directory not found: {input_dir}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    process(input_dir, out_dir, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
