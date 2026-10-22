import csv
from pathlib import Path

from make_synthetic import make_sequence
from shockfront import TrackerConfig, process


def _small_config() -> TrackerConfig:
    return TrackerConfig(
        fps=1000.0,
        bright_threshold=100.0,
        sal_threshold=5.0,
        bar_clearance=10.0,
        min_measured_rows=20,
        fit_tolerance=8.0,
        measure_tolerance=8.0,
        cross_band=None,
        make_gif=True,
        gif_every=2,
        make_contact_sheet=True,
        make_plot=True,
    )


def test_synthetic_end_to_end(tmp_path: Path):
    frames = tmp_path / "frames"
    results = tmp_path / "results"
    make_sequence(frames, n_frames=8, width=320, height=180)

    process(frames, results, _small_config())

    assert (results / "metrics.csv").exists()
    assert (results / "summary.json").exists()
    assert (results / "preview.gif").exists()
    assert (results / "contact_sheet.png").exists()
    assert (results / "curves.png").exists()

    rows = list(csv.DictReader((results / "metrics.csv").open(encoding="utf-8-sig")))
    assert len(rows) == 8
    for row in rows:
        assert row["左侧来源"] in {"measured", "inertia", "none"}
        assert row["右侧来源"] in {"measured", "inertia", "none"}

    overlays = list((results / "frames").glob("*_front.png"))
    assert len(overlays) == 8


def test_single_frame_is_skipped_gracefully(tmp_path: Path):
    frames = tmp_path / "frames"
    results = tmp_path / "results"
    make_sequence(frames, n_frames=1, width=240, height=160)

    process(frames, results, _small_config())

    # With one frame there is no temporal static map or global fit;
    # the pipeline should still write a metrics file.
    assert (results / "metrics.csv").exists()
