# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2025-10-22

### Added

- Row-wise outermost shock-front extraction from image sequences.
- Static-structure suppression for support columns and crossbars.
- Thin bright-edge and moving-arc saliency criteria.
- Robust global motion fitting.
- Occlusion-aware inertial shape coasting with `measured` / `inertia` labels.
- Per-frame overlays, `metrics.csv`, `summary.json`, curves, contact sheet and GIF.
- Synthetic demo generator and end-to-end smoke test.
- MIT license, citation metadata and documentation.

### Known limitations

- Occluded frames are predictions, not measurements.
- The early front may coincide with the fireball edge.
- Absolute accuracy depends on pixel calibration and edge definition.
