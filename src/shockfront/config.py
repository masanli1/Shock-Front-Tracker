#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuration dataclass for the shock-front tracker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TrackerConfig:
    roi_top: Optional[int] = None
    hp_sigma: float = 6.0
    static_percentile: float = 20.0
    bright_threshold: float = 80.0
    sal_threshold: float = 8.0
    run_pixels: int = 2
    bar_pad: int = 4
    cross_band: tuple[int, int] = (114, 130)  # 横梁遮挡行，置空后插值

    median_window: int = 21
    max_deviation: float = 14.0
    max_gap: int = 24
    smooth_window: int = 7
    min_segment_length: int = 20

    min_measured_rows: int = 80
    fit_tolerance: float = 12.0
    measure_tolerance: float = 12.0  # 允许作为实测的轨迹偏差
    fit_iterations: int = 6

    # 遮挡段惯性模型：全局匀速 + 上一次可信曲线形状保持
    inertia_alpha: float = 0.20      # 有可靠实测时形状的缓慢更新增益
    shape_jump_tol: float = 8.0      # 形状突变超过该值时直接替换
    shape_smooth_y: int = 9          # 形状沿曲线方向的平滑窗口
    bar_clearance: float = 20.0      # 前缘距立柱小于该值时视为遮挡/污染，冻结形状

    fps: float = 75000.0

    make_gif: bool = True
    gif_every: int = 2
    gif_width: int = 768
    gif_duration_ms: int = 80
    make_contact_sheet: bool = True
    make_plot: bool = True
    limit: int = 0
