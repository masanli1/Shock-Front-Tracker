from dataclasses import asdict

from shockfront import TrackerConfig


def test_defaults():
    cfg = TrackerConfig()
    assert cfg.hp_sigma == 6.0
    assert cfg.static_percentile == 20.0
    assert cfg.bright_threshold == 80.0
    assert cfg.sal_threshold == 8.0
    assert cfg.bar_clearance == 20.0
    assert cfg.inertia_alpha == 0.2
    assert cfg.shape_smooth_y == 9
    assert cfg.fps == 75000.0


def test_asdict_contains_core_fields():
    data = asdict(TrackerConfig())
    for key in ("hp_sigma", "static_percentile", "bright_threshold",
                "sal_threshold", "bar_clearance", "inertia_alpha"):
        assert key in data
