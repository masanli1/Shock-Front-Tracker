# Parameters

All parameters can be passed on the command line; the same names are available
in `shockfront.TrackerConfig`.

## Detection

| CLI option | Config field | Default | Meaning |
|---|---|---|---|
| `--hp-sigma` | `hp_sigma` | 6.0 | Gaussian sigma of the high-pass response, in pixels |
| `--static-percentile` | `static_percentile` | 20 | temporal percentile used as the static response |
| `--bright-threshold` | `bright_threshold` | 80 | minimum green value for a thin bright edge |
| `--sal-threshold` | `sal_threshold` | 8 | minimum saliency for a moving arc |
| `--bar-pad` | `bar_pad` | 4 | pixels skipped around detected columns |
| `--bar-clearance` | `bar_clearance` | 20 | freeze shape when the front is this close to a column |
| `--roi-top` | `roi_top` | auto | height of the top metadata bar |

## Track cleaning

| CLI option | Config field | Default | Meaning |
|---|---|---|---|
| `--median-window` | `median_window` | 21 | median-filter window for outlier removal |
| `--max-deviation` | `max_deviation` | 14 | outlier threshold in pixels |
| `--max-gap` | `max_gap` | 24 | maximum gap interpolated along the curve |
| `--smooth-window` | `smooth_window` | 7 | moving-average window |
| `--min-measured-rows` | `min_measured_rows` | 80 | minimum valid rows for a measured frame |
| `--fit-tolerance` | `fit_tolerance` | 12 | residual tolerance of the global line |
| `--measure-tolerance` | `measure_tolerance` | 12 | tolerance used to accept a frame as measured |

## Inertia

| CLI option | Config field | Default | Meaning |
|---|---|---|---|
| `--inertia-alpha` | `inertia_alpha` | 0.2 | shape-update gain when the front is clear of columns |
| `--shape-smooth-y` | `shape_smooth_y` | 9 | median smoothing along the curve |
| `--shape-jump-tol` | `shape_jump_tol` | 8 | shape jump that triggers a reference replacement |

## Time and output

| CLI option | Config field | Default | Meaning |
|---|---|---|---|
| `--fps` | `fps` | 75000 | frame rate used for relative time and speed |
| `--no-gif` | `make_gif=False` | off | disable `preview.gif` |
| `--no-contact-sheet` | `make_contact_sheet=False` | off | disable `contact_sheet.png` |
| `--no-plot` | `make_plot=False` | off | disable `curves.png` |
| `--gif-every` | `gif_every` | 2 | take every N-th frame for the GIF |
| `--limit` | `limit` | 0 | process only the first N frames |

## Tuning guide

| Symptom | Change |
|---|---|
| front missed in early frames | lower `--bright-threshold` |
| front missed in late, low-contrast frames | lower `--sal-threshold` |
| columns / crossbars detected as front | increase `--bar-clearance`, lower `--static-percentile` |
| dashed curve too wiggly | increase `--shape-smooth-y` |
| shape changes too fast after occlusion | decrease `--inertia-alpha` |
| measured/inertia switching too often | increase `--fit-tolerance` or `--measure-tolerance` |
| too few measured frames | lower `--min-measured-rows` |
