#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爆炸冲击波前缘全程跟踪程序（含早期段与遮挡段）
================================================
目标：把冲击波前缘从**第一帧**一直跟踪到最后一帧，而不是等到它跑到画面
边缘才显示；中间的立柱遮挡段用虚线标出，绝不画椭圆、不填充爆炸区域。

为什么需要“早期段 + 遮挡段 + 外侧段”
------------------------------------
冲击波从爆炸中心向外扩展，它的前缘在画面中的位置大致是匀速外移的：

  * 早期：前缘还在火球外缘附近（左 x≈200，右 x≈820），表现为一圈很亮的
    细边；它和最外侧的大弧线其实是**同一条前缘**在不同时刻的位置。
  * 中期：前缘走到实验台立柱附近（左 x≈110~140，右 x≈900~940），
    被黑色立柱挡住，单帧里看不到完整弧线。
  * 后期：前缘从立柱另一侧出来（左 x≈100→13，右 x≈950→1008），
    成为画面边缘附近的大弧线。

本程序对每一帧都从画面边缘向里扫描“细亮线或移动显著弧线”，得到前缘
x(y)；再用稳健直线拟合给出整体外移速度，判断哪些帧是实测、哪些帧被立柱遮挡。
遮挡帧按“全局匀速 + 可信曲线形状保持（刚性平移）”外推，并以**虚线**绘制，明确标注“惯性预测”。

依赖：numpy、Pillow
本文件是包的核心实现；命令行入口见 shockfront.cli：
    shockfront track --input <frames_dir> --output <results_dir>
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont



# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


_FONT_CANDIDATES = ['/System/Library/Fonts/Hiragino Sans GB.ttc', '/System/Library/Fonts/STHeiti Medium.ttc', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf', '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/msyh.ttc']


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.float32)

def detect_roi_top(rgb: np.ndarray) -> int:
    """自动寻找顶部黑底参数栏下边界。"""
    gray = rgb.mean(axis=2)
    frac = (gray > 5.0).mean(axis=1)
    for y in range(max(0, len(frac) - 5)):
        if np.all(frac[y:y + 5] > 0.60):
            if y >= 5:
                return int(y)
            break
    return 0

def detect_bars(gray: np.ndarray, ratio: float = 0.22) -> list[tuple[int, int]]:
    """检测贯穿画面的黑色竖直立柱。"""
    med = np.median(gray, axis=0)
    typical = float(np.median(med))
    dark = med < max(6.0, ratio * typical)
    groups: list[tuple[int, int]] = []
    x = 0
    n = len(dark)
    while x < n:
        if not dark[x]:
            x += 1
            continue
        x2 = x
        while x2 + 1 < n and dark[x2 + 1]:
            x2 += 1
        if 3 <= (x2 - x + 1) <= 60:
            groups.append((x, x2))
        x = x2 + 1
    return groups

def gaussian_blur_1channel(img: np.ndarray, sigma: float) -> np.ndarray:
    """可分离高斯模糊（reflect 边界）。"""
    if sigma <= 0:
        return img.astype(np.float32, copy=True)
    radius = max(1, int(round(3.0 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float32)
    k = np.exp(-(x * x) / (2.0 * sigma * sigma))
    k /= k.sum()

    p = np.pad(img, ((0, 0), (radius, radius)), mode="reflect")
    out = np.apply_along_axis(lambda row: np.convolve(row, k, "valid"), 1, p)
    p = np.pad(out, ((radius, radius), (0, 0)), mode="reflect")
    out = np.apply_along_axis(lambda col: np.convolve(col, k, "valid"), 0, p)
    return out.astype(np.float32)

def highpass_response(gray: np.ndarray, sigma: float) -> np.ndarray:
    """绝对值高通：细亮线、细暗线都会得到正响应。"""
    return np.abs(gray - gaussian_blur_1channel(gray, sigma)).astype(np.float32)

def median_filter_track(values: np.ndarray, window: int, max_dev: float,
                        passes: int = 2) -> np.ndarray:
    out = values.astype(np.float64).copy()
    n = len(out)
    half = max(1, window // 2)
    for _ in range(passes):
        for i in range(n):
            if np.isnan(out[i]):
                continue
            seg = out[max(0, i - half):min(n, i + half + 1)]
            med = np.nanmedian(seg)
            if np.isfinite(med) and abs(out[i] - med) > max_dev:
                out[i] = np.nan
    return out

def interpolate_short_gaps(values: np.ndarray, max_gap: int) -> np.ndarray:
    out = values.astype(np.float64).copy()
    valid = np.where(~np.isnan(out))[0]
    if len(valid) < 2:
        return out
    for a, b in zip(valid[:-1], valid[1:]):
        gap = b - a
        if 1 < gap <= max_gap:
            out[a + 1:b] = np.linspace(out[a], out[b], gap + 1)[1:-1]
    return out

def moving_average_track(values: np.ndarray, window: int) -> np.ndarray:
    out = values.astype(np.float64).copy()
    n = len(out)
    half = max(1, window // 2)
    for i in range(n):
        if np.isnan(out[i]):
            continue
        seg = out[max(0, i - half):min(n, i + half + 1)]
        seg = seg[~np.isnan(seg)]
        if len(seg):
            out[i] = float(seg.mean())
    return out

def split_segments(values: np.ndarray, min_len: int) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    n = len(values)
    i = 0
    while i < n:
        if np.isnan(values[i]):
            i += 1
            continue
        j = i
        while j < n and not np.isnan(values[j]):
            j += 1
        if j - i >= min_len:
            segments.append((i, j))
        i = j
    return segments

def build_static_map(files: list[Path], roi_top: int, sigma: float,
                     percentile: float) -> np.ndarray:
    """
    第一遍：计算所有帧的 |高通|，取低分位数作为“静态结构”图。

    静止的立柱、横梁、镜头暗角在所有帧都保持强响应，因此低分位数仍高；
    移动的冲击波只在少数帧经过某个像素，低分位数会被压低。
    """
    stack = []
    for path in files:
        rgb = load_rgb(path)
        gray = rgb[roi_top:, :, 1]
        hp = highpass_response(gray, sigma)
        stack.append(np.clip(hp, 0, 255).astype(np.uint8))
    arr = np.stack(stack, axis=0)
    static = np.percentile(arr, percentile, axis=0).astype(np.float32)
    return static

def load_font(size: int):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()

def enhance(rgb: np.ndarray, gamma: float = 0.9, gain: float = 1.45) -> np.ndarray:
    x = np.clip(rgb, 0, 255) / 255.0
    x = np.power(x, gamma) * gain
    return (np.clip(x, 0, 1) * 255.0).astype(np.uint8)

def make_gif(frames: list[Image.Image], out_path: Path, every: int,
             width: int, duration: int) -> None:
    if not frames:
        return
    selected = frames[::max(1, every)]
    out = []
    for im in selected:
        h = int(im.height * width / im.width)
        out.append(im.resize((width, h), Image.LANCZOS).convert(
            "P", palette=Image.ADAPTIVE, colors=128))
    out[0].save(out_path, save_all=True, append_images=out[1:],
                duration=duration, loop=0, optimize=True, disposal=2)

def make_contact_sheet(items: list[tuple[Path, Image.Image]], out_path: Path,
                       cols: int = 3, tile_w: int = 520) -> None:
    if not items:
        return
    aspect = items[0][1].height / items[0][1].width
    tile_h = int(tile_w * aspect)
    rows = math.ceil(len(items) / cols)
    cap = 24
    sheet = Image.new("RGB", (cols * tile_w, rows * (tile_h + cap)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    font = load_font(15)
    for i, (path, img) in enumerate(items):
        x = (i % cols) * tile_w
        y = (i // cols) * (tile_h + cap)
        sheet.paste(img.resize((tile_w, tile_h), Image.LANCZOS), (x, y + cap))
        draw.text((x + 6, y + 2), path.stem, font=font, fill=(255, 255, 255))
    sheet.save(out_path)


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------

from .config import TrackerConfig


@dataclass
class Track:
    x: np.ndarray          # 每行的前缘 x
    strength: np.ndarray
    segments: list[tuple[int, int]]
    source: str            # "measured" / "inertia" / "none"


@dataclass
class Metric:
    file: str
    frame_no: int
    time_ms: float
    left_x_mid: float
    right_x_mid: float
    width_mid: float
    center_x_mid: float
    left_x_quarter: float
    right_x_quarter: float
    left_x_three_quarter: float
    right_x_three_quarter: float
    left_valid_rows: int
    right_valid_rows: int
    left_strength: float
    right_strength: float
    left_speed_px_ms: float
    right_speed_px_ms: float
    width_speed_px_ms: float
    confidence: float
    left_source: str
    right_source: str
    left_visible: bool
    right_visible: bool


# ---------------------------------------------------------------------------
# 单行扫描：细亮线 或 移动显著弧线
# ---------------------------------------------------------------------------

def scan_row(gray: np.ndarray, sal: np.ndarray, y: int,
             x_edge: int, x_inner: int, bars: list[tuple[int, int]],
             cfg: TrackerConfig) -> tuple[float, float, str]:
    step = 1 if x_inner > x_edge else -1
    xs = np.arange(x_edge, x_inner, step, dtype=int)
    if len(xs) < cfg.run_pixels:
        return (np.nan, 0.0, "")

    v = gray[y, xs].astype(np.float64)
    s = sal[y, xs].astype(np.float64)

    # 屏蔽立柱及其边缘
    masked = np.zeros(len(xs), dtype=bool)
    for a, b in bars:
        masked |= (xs >= a - cfg.bar_pad) & (xs <= b + cfg.bar_pad)
    v = np.where(masked, -999.0, v)
    s = np.where(masked, -999.0, s)

    bright = v > cfg.bright_threshold
    i = 0
    n = len(xs)
    while i < n:
        # 1) 细亮线：宽度 1~12，且内侧有暗缝
        if bright[i]:
            j = i
            while j + 1 < n and bright[j + 1]:
                j += 1
            if 1 <= (j - i + 1) <= 12:
                k0 = min(n - 1, j + 1)
                k1 = min(n - 1, j + 15)
                if k1 > k0 and v[k0:k1 + 1].min() < 0.6 * cfg.bright_threshold:
                    return (float(np.mean(xs[i:j + 1])),
                            float(v[i:j + 1].max()), "bright")
            i = j + 1
            continue

        # 2) 移动显著弧线：连续 run_pixels 个点显著度超阈值
        if i + cfg.run_pixels <= n and np.all(
                s[i:i + cfg.run_pixels] > cfg.sal_threshold):
            return (float(xs[i]), float(s[i]), "sal")
        i += 1

    return (np.nan, 0.0, "")


def scan_frame(gray: np.ndarray, sal: np.ndarray,
               left_region: tuple[int, int], right_region: tuple[int, int],
               bars: list[tuple[int, int]],
               cfg: TrackerConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    h = gray.shape[0]
    lx = np.full(h, np.nan)
    rx = np.full(h, np.nan)
    ls = np.zeros(h)
    rs = np.zeros(h)
    for y in range(h):
        x, v, _ = scan_row(gray, sal, y, left_region[0], left_region[1],
                           bars, cfg)
        lx[y] = x
        ls[y] = v
        x, v, _ = scan_row(gray, sal, y, right_region[0], right_region[1],
                           bars, cfg)
        rx[y] = x
        rs[y] = v
    if cfg.cross_band is not None:
        y0, y1 = cfg.cross_band
        lx[max(0, y0):max(0, y1)] = np.nan
        rx[max(0, y0):max(0, y1)] = np.nan
    return lx, ls, rx, rs


# ---------------------------------------------------------------------------
# 轨迹整理与稳健拟合
# ---------------------------------------------------------------------------

def clean(values: np.ndarray, cfg: TrackerConfig) -> np.ndarray:
    out = median_filter_track(values, cfg.median_window,
                                   cfg.max_deviation)
    out = interpolate_short_gaps(out, cfg.max_gap)
    out = moving_average_track(out, cfg.smooth_window)
    return out


def robust_line(med: np.ndarray, valid: np.ndarray,
                cfg: TrackerConfig) -> tuple[float, float, np.ndarray]:
    """对中位位置做稳健直线拟合，返回 (slope, intercept, inlier_mask)。"""
    t = np.arange(len(med), dtype=np.float64)
    ok = np.isfinite(med) & (valid >= cfg.min_measured_rows)
    if ok.sum() < 5:
        # 数据不足时使用首尾两点
        idx = np.where(np.isfinite(med))[0]
        if len(idx) < 2:
            return (0.0, float(np.nanmean(med)) if np.isfinite(med).any() else 0.0,
                    np.zeros(len(med), dtype=bool))
        slope = (med[idx[-1]] - med[idx[0]]) / max(1e-9, idx[-1] - idx[0])
        intercept = med[idx[0]] - slope * idx[0]
        return (slope, intercept, np.isfinite(med))

    coef = np.polyfit(t[ok], med[ok], 1)
    for _ in range(cfg.fit_iterations):
        pred = np.polyval(coef, t)
        ok2 = ok & (np.abs(med - pred) <= cfg.fit_tolerance)
        if ok2.sum() < 5:
            break
        coef = np.polyfit(t[ok2], med[ok2], 1)
    pred = np.polyval(coef, t)
    inliers = ok & (np.abs(med - pred) <= cfg.fit_tolerance)
    return (float(coef[0]), float(coef[1]), inliers)



def smooth_along_y(values: np.ndarray, window: int = 9) -> np.ndarray:
    """沿曲线方向做小窗口中值平滑；只去毛刺，不改变整体形状。"""
    n = len(values)
    out = values.copy()
    half = max(1, window // 2)
    for y in range(n):
        if not np.isfinite(values[y]):
            continue
        seg = values[max(0, y - half):min(n, y + half + 1)]
        seg = seg[np.isfinite(seg)]
        if len(seg):
            out[y] = float(np.median(seg))
    return out


def build_side_tracks(raw_curves: list[np.ndarray],
                      strengths: list[np.ndarray],
                      bars: list[tuple[int, int]],
                      cfg: TrackerConfig) -> tuple[list[Track], float, float]:
    """
    由每帧原始 x(y) 生成全程轨迹。

    遮挡段采用“全局匀速 + 可信形状保持”的惯性模型：

      * 全局轨迹 m(t)=a·t+b 提供整体外移速度；
      * 保存最近一次“可信”的整条曲线 x_ref(y)（不是多项式近似）；
      * 遮挡帧只做刚性平移：x_t(y) = x_ref(y) + [m(t) − m(t_ref)]；
      * 只有当前缘远离立柱、且连续可靠出现时，才用增益 alpha 缓慢更新形状；
      * 因此遮挡段形状逐像素保持不变，只发生整体移动，不会被拉弯/拉直。
    """
    n = len(raw_curves)
    h = raw_curves[0].shape[0] if n else 0
    mid = np.array([value_at(c, h // 2) if np.isfinite(c).any() else np.nan
                    for c in raw_curves], dtype=np.float64)
    valid = np.array([int(np.isfinite(c).sum()) for c in raw_curves], dtype=int)
    slope, intercept, inliers = robust_line(mid, valid, cfg)
    if not np.isfinite(slope):
        slope = 0.0
    fit = slope * np.arange(n) + intercept

    measured = ((valid >= cfg.min_measured_rows)
                & np.isfinite(mid)
                & (np.abs(mid - fit) <= cfg.measure_tolerance))

    # 离立柱太近时，检测容易抓到立柱/火焰边缘，不允许更新形状
    near_bar = np.zeros(n, dtype=bool)
    if bars and cfg.bar_clearance > 0:
        for b0, b1 in bars:
            near_bar |= ((mid >= b0 - cfg.bar_clearance)
                         & (mid <= b1 + cfg.bar_clearance))
    trusted = measured & ~near_bar

    cleaned: list[np.ndarray] = []
    for c in raw_curves:
        cleaned.append(clean(c, cfg) if np.isfinite(c).any() else c)

    shape_ref: Optional[np.ndarray] = None
    ref_t = 0
    clear_run = 0
    last_curve: Optional[np.ndarray] = None
    last_t = 0
    in_occlusion = False
    history: list[tuple[int, np.ndarray]] = []

    # 用第一个可信帧初始化，保证第一帧及之前的帧也有曲线
    first_idx = np.where(trusted)[0]
    if len(first_idx):
        ref_t = int(first_idx[0])
        shape_ref = smooth_along_y(cleaned[ref_t], cfg.shape_smooth_y)
        last_curve = shape_ref.copy()
        last_t = ref_t

    tracks: list[Track] = []
    for i in range(n):
        if trusted[i]:
            clear_run += 1
        else:
            clear_run = 0

        # 遮挡开始：把“最后一次可信的整条曲线”原样冻结为惯性形状
        if (not trusted[i]) and (not in_occlusion) and last_curve is not None:
            if len(history) >= 3:
                # 在最近的可信曲线中选“弯曲程度最大”的一条作为惯性形状，
                # 避免立柱附近逐渐变直的检测把弧线拉平。
                best_k = 0
                best_range = -1.0
                for k, (_, c) in enumerate(history):
                    r = c[np.isfinite(c)]
                    if len(r) < 8:
                        continue
                    rr = float(np.max(r) - np.min(r))
                    if rr > best_range:
                        best_range = rr
                        best_k = k
                ref_t, ref_curve = history[best_k]
                shape_ref = ref_curve.copy()
            else:
                shape_ref = last_curve.copy()
                ref_t = last_t
            in_occlusion = True

        if trusted[i]:
            last_curve = smooth_along_y(cleaned[i], cfg.shape_smooth_y)
            last_t = i
            if not in_occlusion:
                history.append((i, last_curve.copy()))
                if len(history) > 7:
                    history.pop(0)
            if shape_ref is None:
                shape_ref = last_curve.copy()
                ref_t = i
            elif (not in_occlusion) and clear_run >= 3 and i - ref_t >= 3:
                # 连续可靠且已离开遮挡：缓慢更新形状
                z_aligned = last_curve - fit[i] + fit[ref_t]
                diff = z_aligned - shape_ref
                diff = diff[np.isfinite(diff)]
                jump = float(np.median(np.abs(diff - np.median(diff)))) if len(diff) else 0.0
                if jump <= cfg.shape_jump_tol:
                    shape_ref = ((1.0 - cfg.inertia_alpha) * shape_ref
                                 + cfg.inertia_alpha * z_aligned)
                else:
                    shape_ref = z_aligned
                    ref_t = i
            if clear_run >= 3 and i - ref_t >= 3:
                in_occlusion = False

        if shape_ref is None:
            curve = np.full(h, np.nan, dtype=np.float64)
            source = "none"
        else:
            curve = shape_ref + (fit[i] - fit[ref_t])
            source = "measured" if trusted[i] else "inertia"

        segs = split_segments(curve, cfg.min_segment_length)
        if not segs:
            source = "none"
        tracks.append(Track(
            x=curve,
            strength=strengths[i] if i < len(strengths) else np.zeros(h),
            segments=segs,
            source=source,
        ))
    return tracks, slope, intercept


# ---------------------------------------------------------------------------
# 指标
# ---------------------------------------------------------------------------

def value_at(values: np.ndarray, y: int) -> float:
    if 0 <= y < len(values) and np.isfinite(values[y]):
        return float(values[y])
    idx = np.where(np.isfinite(values))[0]
    if len(idx) == 0:
        return float("nan")
    k = int(idx[np.argmin(np.abs(idx - y))])
    return float(values[k])


def compute_metrics(files: list[Path], numbers: list[int],
                    times: list[float],
                    left: list[Track], right: list[Track]) -> list[Metric]:
    h = left[0].x.shape[0] if left else 1
    ys = [int(0.25 * h), int(0.50 * h), int(0.75 * h)]
    metrics: list[Metric] = []
    for i in range(len(files)):
        lm = value_at(left[i].x, ys[1])
        rm = value_at(right[i].x, ys[1])
        l_ok = left[i].source != "none" and np.isfinite(lm)
        r_ok = right[i].source != "none" and np.isfinite(rm)
        lm = lm if l_ok else float("nan")
        rm = rm if r_ok else float("nan")
        width = (rm - lm) if np.isfinite(lm) and np.isfinite(rm) else float("nan")
        center = ((lm + rm) / 2.0) if np.isfinite(width) else float("nan")

        lv = int(np.isfinite(left[i].x).sum())
        rv = int(np.isfinite(right[i].x).sum())
        ls = float(np.nanmean(left[i].strength)) if lv else 0.0
        rs = float(np.nanmean(right[i].strength)) if rv else 0.0

        metrics.append(Metric(
            file=files[i].name, frame_no=numbers[i], time_ms=times[i],
            left_x_mid=lm, right_x_mid=rm, width_mid=width,
            center_x_mid=center,
            left_x_quarter=value_at(left[i].x, ys[0]) if l_ok else float("nan"),
            right_x_quarter=value_at(right[i].x, ys[0]) if r_ok else float("nan"),
            left_x_three_quarter=value_at(left[i].x, ys[2]) if l_ok else float("nan"),
            right_x_three_quarter=value_at(right[i].x, ys[2]) if r_ok else float("nan"),
            left_valid_rows=lv, right_valid_rows=rv,
            left_strength=ls, right_strength=rs,
            left_speed_px_ms=float("nan"), right_speed_px_ms=float("nan"),
            width_speed_px_ms=float("nan"),
            confidence=(lv + rv) / (2.0 * h) if h else 0.0,
            left_source=left[i].source, right_source=right[i].source,
            left_visible=l_ok, right_visible=r_ok,
        ))

    # 速度用 ±4 帧窗口线性拟合，避免逐帧抖动
    n = len(metrics)
    for i, m in enumerate(metrics):
        lo, hi = max(0, i - 4), min(n, i + 4 + 1)
        window = metrics[lo:hi]
        t = [w.time_ms for w in window]

        def slope(vals: list[float]) -> float:
            pts = [(tt, vv) for tt, vv in zip(t, vals) if np.isfinite(vv)]
            if len(pts) < 2:
                return float("nan")
            tt = np.array([p[0] for p in pts], float)
            vv = np.array([p[1] for p in pts], float)
            if tt.max() - tt.min() <= 0:
                return float("nan")
            return float(np.polyfit(tt, vv, 1)[0])

        lslope = slope([w.left_x_mid for w in window])
        rslope = slope([w.right_x_mid for w in window])
        m.left_speed_px_ms = -lslope if np.isfinite(lslope) else float("nan")
        m.right_speed_px_ms = rslope if np.isfinite(rslope) else float("nan")
        m.width_speed_px_ms = (rslope - lslope) if (np.isfinite(lslope) and np.isfinite(rslope)) else float("nan")
    return metrics


# ---------------------------------------------------------------------------
# 绘图
# ---------------------------------------------------------------------------

def dashed_polyline(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]],
                    color: tuple[int, int, int], width: int = 3,
                    dash: int = 9, gap: int = 6) -> None:
    if len(pts) < 2:
        return
    on = True
    remain = dash
    prev = pts[0]
    for cur in pts[1:]:
        x0, y0 = prev
        x1, y1 = cur
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg <= 1e-9:
            prev = cur
            continue
        pos = 0.0
        while pos < seg:
            step = min(remain, seg - pos)
            a = pos / seg
            b = (pos + step) / seg
            if on:
                draw.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a),
                           (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)],
                          fill=color, width=width)
            pos += step
            remain -= step
            if remain <= 1e-9:
                on = not on
                remain = dash if on else gap
        prev = cur


def draw_track(draw: ImageDraw.ImageDraw, tr: Track, offset: int,
               color: tuple[int, int, int]) -> None:
    for a, b in tr.segments:
        pts = [(float(tr.x[y]), float(y + offset)) for y in range(a, b)]
        if tr.source == "measured":
            if len(pts) >= 2:
                draw.line(pts, fill=color, width=3, joint="curve")
        else:
            dashed_polyline(draw, pts, color, width=3)


def annotate(rgb: np.ndarray, roi_top: int, left: Track, right: Track,
             m: Metric, cfg: TrackerConfig) -> Image.Image:
    img = Image.fromarray(enhance(rgb))
    draw = ImageDraw.Draw(img)
    font = load_font(18)
    small = load_font(15)
    off = roi_top

    if m.left_visible:
        draw_track(draw, left, off, (255, 60, 60))
    if m.right_visible:
        draw_track(draw, right, off, (0, 230, 255))

    h = left.x.shape[0]
    y_mid = h // 2
    for tr, x, color, sign in ((left, m.left_x_mid, (255, 60, 60), -1),
                               (right, m.right_x_mid, (0, 230, 255), 1)):
        if not np.isfinite(x) or tr.source == "none":
            continue
        x = float(x)
        draw.line([(x, y_mid + off), (x + sign * 30, y_mid + off)],
                  fill=color, width=2)
        draw.polygon([(x + sign * 34, y_mid + off),
                      (x + sign * 24, y_mid + off - 6),
                      (x + sign * 24, y_mid + off + 6)], fill=color)

    title = "冲击波前缘（实线=实测，虚线=惯性预测）"
    tw = draw.textlength(title, font=font)
    draw.rectangle([img.width - tw - 26, off + 8, img.width - 8, off + 36],
                   fill=(0, 0, 0, 160))
    draw.text((img.width - tw - 18, off + 10), title, font=font,
              fill=(255, 255, 0))

    def src_label(s: str) -> str:
        return {"measured": "实测", "inertia": "惯性预测", "none": "不可见"}.get(s, s)

    lt = f"{m.left_x_mid:.1f} px" if m.left_visible else "不可见"
    rt = f"{m.right_x_mid:.1f} px" if m.right_visible else "不可见"
    wt = f"{m.width_mid:.1f} px" if m.left_visible and m.right_visible else "—"
    lines = [
        f"{m.file}   序号 {m.frame_no}   Δt={m.time_ms:+.4f} ms",
        f"左 {lt}（{src_label(m.left_source)}）  右 {rt}（{src_label(m.right_source)}）",
        f"间距 {wt}   置信度 {m.confidence:.0%}",
    ]
    if np.isfinite(m.left_speed_px_ms) or np.isfinite(m.right_speed_px_ms):
        ls = f"{m.left_speed_px_ms:.0f}" if np.isfinite(m.left_speed_px_ms) else "-"
        rs = f"{m.right_speed_px_ms:.0f}" if np.isfinite(m.right_speed_px_ms) else "-"
        lines.append(f"外扩速度 左 {ls} / 右 {rs} px/ms")

    box_w = max(draw.textlength(s, font=small) for s in lines) + 16
    box_h = len(lines) * 19 + 8
    draw.rectangle([8, off + 6, 8 + box_w, off + 6 + box_h],
                   fill=(0, 0, 0, 160))
    ty = off + 10
    for s in lines:
        draw.text((14, ty), s, font=small, fill=(230, 255, 230))
        ty += 19

    return img


def draw_curves(metrics: list[Metric], out_path: Path) -> None:
    if not metrics:
        return
    W, H = 1100, 760
    left, right, top, bottom = 86, 30, 90, 54
    gap = 66
    panel_h = (H - top - bottom - gap) // 2
    img = Image.new("RGB", (W, H), (250, 250, 248))
    draw = ImageDraw.Draw(img)
    font = load_font(19)
    small = load_font(14)
    title_font = load_font(22)

    times = [m.time_ms for m in metrics]
    xmin, xmax = min(times), max(times)
    if xmax <= xmin:
        xmax = xmin + 1

    panels = [
        ("冲击波左、右前缘位置 / px",
         [("左前缘", [m.left_x_mid for m in metrics], (230, 70, 70)),
          ("右前缘", [m.right_x_mid for m in metrics], (0, 150, 220))]),
        ("左右前缘间距 / px",
         [("间距", [m.width_mid for m in metrics], (40, 150, 90))]),
    ]

    for pi, (title, series) in enumerate(panels):
        y_top = top + pi * (panel_h + gap)
        y_bot = y_top + panel_h
        draw.rectangle([left, y_top, W - right, y_bot], fill=(255, 255, 255),
                       outline=(180, 180, 180))
        allv = [v for _, vals, _ in series for v in vals if np.isfinite(v)]
        if not allv:
            continue
        vmin, vmax = min(allv), max(allv)
        if vmax <= vmin:
            vmax = vmin + 1
        pad = (vmax - vmin) * 0.08
        vmin -= pad
        vmax += pad

        def sx(t):
            return left + (t - xmin) / (xmax - xmin) * (W - left - right)

        def sy(v):
            return y_bot - (v - vmin) / (vmax - vmin) * panel_h

        for gi in range(6):
            v = vmin + (vmax - vmin) * gi / 5
            y = sy(v)
            draw.line([(left, y), (W - right, y)], fill=(232, 232, 232))
            draw.text((8, y - 8), f"{v:,.0f}", font=small, fill=(90, 90, 90))
        for gi in range(6):
            t = xmin + (xmax - xmin) * gi / 5
            x = sx(t)
            draw.line([(x, y_top), (x, y_bot)], fill=(240, 240, 240))
            label = f"{t:.3f}"
            tw = draw.textlength(label, font=small)
            draw.text((x - tw / 2, y_bot + 5), label, font=small,
                      fill=(90, 90, 90))

        for name, vals, col in series:
            pts = [(sx(t), sy(v)) for t, v in zip(times, vals) if np.isfinite(v)]
            if len(pts) >= 2:
                draw.line(pts, fill=col, width=2)
        draw.text((left + 4, y_top - 30), title, font=font, fill=(40, 40, 40))

        lx = W - right - 140
        ly = y_top + 8
        for name, vals, col in series:
            draw.line([(lx, ly + 8), (lx + 24, ly + 8)], fill=col, width=3)
            draw.text((lx + 30, ly), name, font=small, fill=(60, 60, 60))
            ly += 20

    draw.text((left, 14), "爆炸冲击波前缘位置随时间变化（全程）", font=title_font,
              fill=(20, 20, 20))
    tw = draw.textlength("时间 t / ms", font=font)
    draw.text(((W - tw) / 2, H - 28), "时间 t / ms", font=font,
              fill=(40, 40, 40))
    img.save(out_path)


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def write_csv(metrics: list[Metric], path: Path) -> None:
    fields = list(Metric.__dataclass_fields__.keys())
    headers = ["文件名", "帧序号", "相对时间_ms",
               "左前缘x_px", "右前缘x_px", "前缘间距_px", "中心x_px",
               "1/4高度左前缘x_px", "1/4高度右前缘x_px",
               "3/4高度左前缘x_px", "3/4高度右前缘x_px",
               "左有效行数", "右有效行数", "左平均强度", "右平均强度",
               "左外扩速度_px_ms", "右外扩速度_px_ms", "间距增长速度_px_ms",
               "置信度", "左侧来源", "右侧来源", "左可见", "右可见"]
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(headers)
        for m in metrics:
            row = []
            for f in fields:
                v = getattr(m, f)
                row.append(f"{v:.4f}" if isinstance(v, float) else v)
            w.writerow(row)


def write_readme(out_dir: Path, cfg: TrackerConfig, metrics: list[Metric]) -> None:
    n = len(metrics)
    n_meas_l = sum(1 for m in metrics if m.left_source == "measured")
    n_int_l = sum(1 for m in metrics if m.left_source == "inertia")
    n_meas_r = sum(1 for m in metrics if m.right_source == "measured")
    n_int_r = sum(1 for m in metrics if m.right_source == "inertia")
    first = metrics[0]
    last = metrics[-1]
    text = f"""# 爆炸冲击波前缘全程跟踪结果

## 1. 结果概览

- 处理帧数：**{n}**
- 左前缘：实测 **{n_meas_l}** 帧，惯性预测 **{n_int_l}** 帧
- 右前缘：实测 **{n_meas_r}** 帧，惯性预测 **{n_int_r}** 帧
- 帧率：**{cfg.fps:g} fps**
- 时间范围：**{first.time_ms:.4f} – {last.time_ms:.4f} ms**
- 首帧左/右前缘：**{first.left_x_mid:.1f} / {first.right_x_mid:.1f} px**
- 末帧左/右前缘：**{last.left_x_mid:.1f} / {last.right_x_mid:.1f} px**

## 2. 识别对象与“早期段”

本程序识别的是**冲击波前缘**，不是中间爆炸区域：

- 早期：前缘还在火球外缘附近（左 x≈200，右 x≈820），是一圈很亮的细边；
- 中期：前缘经过实验台立柱（左 x≈110~140，右 x≈900~940），被立柱挡住；
- 后期：前缘从立柱另一侧出来（左 x≈100→13，右 x≈950→1008），
  成为画面边缘附近的大弧线。

这三段其实是**同一条前缘**在不同时刻的位置。程序对每帧都从画面边缘向里
扫描“细亮线或移动显著弧线”，并用稳健直线拟合给出整体外移速度：

- **实线**：该帧真正检测到前缘；
- **虚线**：该帧前缘被立柱遮挡或对比度不足，按“全局匀速 + 可信曲线形状保持（刚性平移）”
  外推，明确标注“惯性预测”，不是椭圆拟合，也不会用未来帧把曲线掰弯。

## 3. 输出文件

| 文件 | 内容 |
|---|---|
| `frames/` | 每帧标注图：红=左前缘，青=右前缘；实线实测，虚线惯性预测 |
| `metrics.csv` | 前缘位置、间距、速度、来源（measured/inertia）、可见性 |
| `preview.gif` | 全程慢放动图（默认每 {cfg.gif_every} 帧取 1 帧） |
| `contact_sheet.png` | 9 帧代表性结果（覆盖早期/遮挡/后期） |
| `curves.png` | 左右前缘位置、间距全程曲线 |
| `summary.json` | 参数与统计摘要 |

## 4. 调参

| 参数 | 含义 |
|---|---|
| `--bright-threshold` | 早期亮边阈值；漏检时降低 |
| `--sal-threshold` | 后期/弱弧线显著度阈值；漏检时降低 |
| `--fit-tolerance` | 判定“实测”与直线轨迹的允许偏差（px） |
| `--min-measured-rows` | 判定实测所需的最少有效行数 |
| `--median-window` | 去野值窗口；抖动大时增大 |

## 5. 注意

- 虚线表示立柱遮挡/对比度不足时的惯性预测，不是直接观测到的弧线。
- 早期亮边与后期大弧线是同一条前缘的连续轨迹；如果只需要“完全实测”的
  部分，可查看 CSV 中 `左侧来源/右侧来源 = measured` 的帧。
- `time_ms` 是按帧率计算的相对时间，未对顶部文字做 OCR。

## 6. 复现命令

```bash
python3 shock_full_track.py --input "数据 2" --output "{out_dir.name}" \\
    --fps {cfg.fps:g} --bright-threshold {cfg.bright_threshold:g} --sal-threshold {cfg.sal_threshold:g}
```
"""
    (out_dir / "README.md").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def collect(folder: Path, limit: int) -> list[Path]:
    files = sorted(p for p in folder.iterdir()
                   if p.is_file() and p.suffix.lower() in EXTS)
    return files[:limit] if limit > 0 else files


def parse_no(path: Path, fallback: int) -> int:
    tail = path.stem.split("-")[-1]
    if tail.isdigit():
        return int(tail)
    m = re.search(r"(\d+)$", path.stem)
    return int(m.group(1)) if m else fallback


def process(input_dir: Path, out_dir: Path, cfg: TrackerConfig) -> None:
    files = collect(input_dir, cfg.limit)
    if not files:
        print("错误：没有图像。", file=sys.stderr)
        return

    rgb0 = load_rgb(files[0])
    roi_top = detect_roi_top(rgb0) if cfg.roi_top is None else int(cfg.roi_top)
    roi_top = max(0, min(roi_top, rgb0.shape[0] - 8))
    gray0 = rgb0[roi_top:, :, 1]
    bars = detect_bars(gray0)
    h, w = gray0.shape
    left_region = (0, min(w - 1, 360))
    right_region = (w - 1, max(0, w - 360))
    print(f"参数栏 {roi_top}px；立柱 {bars}")
    print(f"扫描：左 {left_region}，右 {right_region}")

    t0 = time.time()
    print("第一遍：静态高响应图 ...")
    static = build_static_map(files, roi_top, cfg.hp_sigma,
                                   cfg.static_percentile)
    print(f"  完成 {time.time() - t0:.1f}s")

    numbers = [parse_no(p, i + 1) for i, p in enumerate(files)]
    tbase = numbers[0]
    times = [(n - tbase) / cfg.fps * 1000.0 for n in numbers]

    left_curves: list[np.ndarray] = []
    right_curves: list[np.ndarray] = []
    left_strengths: list[np.ndarray] = []
    right_strengths: list[np.ndarray] = []
    rgbs: list[np.ndarray] = []

    print("第二遍：逐帧扫描前缘 ...")
    for i, path in enumerate(files):
        rgb = load_rgb(path)
        gray = rgb[roi_top:, :, 1]
        hp = highpass_response(gray, cfg.hp_sigma)
        sal = hp - static
        lx, ls, rx, rs = scan_frame(gray, sal, left_region, right_region,
                                    bars, cfg)
        left_curves.append(lx)
        right_curves.append(rx)
        left_strengths.append(ls)
        right_strengths.append(rs)
        rgbs.append(rgb)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(files)}")

    print("轨迹拟合与遮挡段惯性外推 ...")
    left_tracks, l_slope, l_intercept = build_side_tracks(left_curves, left_strengths, bars, cfg)
    right_tracks, r_slope, r_intercept = build_side_tracks(right_curves, right_strengths, bars, cfg)

    metrics = compute_metrics(files, numbers, times, left_tracks, right_tracks)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    gif_frames = []
    for i, path in enumerate(files):
        img = annotate(rgbs[i], roi_top, left_tracks[i], right_tracks[i],
                       metrics[i], cfg)
        img.save(frames_dir / f"{path.stem}_front.png")
        gif_frames.append(img.crop((0, roi_top, img.width, img.height)))

    write_csv(metrics, out_dir / "metrics.csv")
    if cfg.make_gif and len(gif_frames) >= 2:
        make_gif(gif_frames, out_dir / "preview.gif", cfg.gif_every,
                      cfg.gif_width, cfg.gif_duration_ms)
    if cfg.make_contact_sheet:
        idx = np.linspace(0, len(files) - 1, min(9, len(files))).astype(int)
        items = []
        for k in idx:
            p = files[int(k)]
            fp = frames_dir / f"{p.stem}_front.png"
            if fp.exists():
                with Image.open(fp) as im:
                    rgb = im.convert("RGB")
                    items.append((p, rgb.crop((0, roi_top, rgb.width, rgb.height))))
        make_contact_sheet(items, out_dir / "contact_sheet.png")
    if cfg.make_plot:
        draw_curves(metrics, out_dir / "curves.png")

    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(out_dir),
        "n_images": len(files),
        "n_left_measured": sum(1 for m in metrics if m.left_source == "measured"),
        "n_left_inertia": sum(1 for m in metrics if m.left_source == "inertia"),
        "n_right_measured": sum(1 for m in metrics if m.right_source == "measured"),
        "n_right_inertia": sum(1 for m in metrics if m.right_source == "inertia"),
        "left_fit": {"slope_px_per_frame": l_slope, "intercept_px": l_intercept},
        "right_fit": {"slope_px_per_frame": r_slope, "intercept_px": r_intercept},
        "config": asdict(cfg),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_readme(out_dir, cfg, metrics)

    print(f"\n完成，输出：{out_dir}")
    print(f"总耗时：{time.time() - t0:.1f}s")
