#!/usr/bin/env python3
"""Generate a small synthetic high-speed sequence for a smoke test/demo."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def make_sequence(out_dir: Path, n_frames: int = 16, width: int = 640,
                  height: int = 360, seed: int = 7) -> None:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    yy, xx = np.mgrid[0:height, 0:width]
    cx, cy = width / 2, height / 2

    for i in range(n_frames):
        g = np.full((height, width), 20.0, dtype=np.float32)
        # dim central fireball
        blob = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * 80.0 ** 2)))
        g += 55.0 * blob
        # expanding bright side arcs (parabolas), no top/bottom closure
        r = 110.0 + 3.5 * i
        curve = 0.0009 * (yy - cy) ** 2
        left_x = (cx - r) - curve
        right_x = (cx + r) + curve
        ring = (np.exp(-((xx - left_x) ** 2) / (2 * 1.2 ** 2))
                + np.exp(-((xx - right_x) ** 2) / (2 * 1.2 ** 2)))
        g += 170.0 * ring
        # dark shadow just outside each arc
        shadow = (np.exp(-((xx - (left_x - 4.0)) ** 2) / (2 * 2.0 ** 2))
                  + np.exp(-((xx - (right_x + 4.0)) ** 2) / (2 * 2.0 ** 2)))
        g -= 18.0 * shadow
        # static vertical support column
        g[:, 70:80] = 2.0
        # noise
        g += rng.normal(0, 2.0, (height, width))
        g = np.clip(g, 0, 255)
        rgb = np.stack([g * 0.08, g, g * 0.10], axis=-1).astype(np.uint8)
        Image.fromarray(rgb).save(out_dir / f"{i + 1:06d}.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="examples/synthetic")
    ap.add_argument("--frames", type=int, default=12)
    args = ap.parse_args()
    make_sequence(Path(args.output), args.frames)
    print(f"wrote {args.frames} frames to {args.output}")
