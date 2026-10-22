# Outputs

```text
results/
├── frames/
│   ├── 000001_front.png
│   ├── 000002_front.png
│   └── ...
├── metrics.csv
├── summary.json
├── curves.png
├── contact_sheet.png
├── preview.gif
└── README.md
```

## `frames/*_front.png`

Per-frame overlay:

- red: left front
- cyan: right front
- solid: measured
- dashed: inertial prediction
- arrows: outward direction at mid-height

## `metrics.csv`

One row per frame. The default header is Chinese for compatibility with the
original experiment workflow; the column order is stable.

| Column | Meaning |
|---|---|
| `文件名` | input filename |
| `帧序号` | frame number parsed from the filename |
| `相对时间_ms` | relative time from frame index and fps |
| `左前缘x_px`, `右前缘x_px` | front position at mid-height |
| `前缘间距_px` | right minus left |
| `中心x_px` | midpoint |
| `1/4高度…`, `3/4高度…` | positions at 25 % and 75 % height |
| `左有效行数`, `右有效行数` | valid rows per side |
| `左平均强度`, `右平均强度` | mean response strength |
| `左外扩速度_px_ms`, `右外扩速度_px_ms` | outward speed |
| `间距增长速度_px_ms` | width growth rate |
| `置信度` | valid-row fraction |
| `左侧来源`, `右侧来源` | `measured`, `inertia`, `none` |
| `左可见`, `右可见` | boolean visibility flags |

For downstream code, prefer the English field names from
`shockfront.core.Metric`; a future release will add `--locale en` to write an
English header directly.

## `summary.json`

Contains:

- input/output paths,
- number of images and detected frames,
- measured / inertia counts,
- fitted slope and intercept per side,
- full configuration,
- basic statistics.

## `preview.gif`, `contact_sheet.png`, `curves.png`

- `preview.gif`: downscaled animation, every `gif_every` frames.
- `contact_sheet.png`: nine representative frames.
- `curves.png`: left/right position and width versus time.
