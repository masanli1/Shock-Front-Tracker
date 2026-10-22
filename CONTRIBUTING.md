# Contributing

Thanks for your interest in improving Shock-Front Tracker.

## Development setup

```bash
git clone https://github.com/masanli1/shock-front-tracker.git
cd shock-front-tracker
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## What to contribute

- Bug reports with a minimal reproducible example (synthetic frames are ideal).
- Improvements to the row-wise scan or inertial model.
- Documentation, parameter guidance, and translations.
- Tests for edge cases: no bars, no visible front, front leaving the frame.

Please do **not** upload experimental data unless you have permission to publish it.
Use `examples/make_synthetic.py` for reproducible test cases.

## Pull requests

1. Open an issue first for non-trivial changes.
2. Keep changes focused; avoid unrelated formatting churn.
3. Run `pytest` and `ruff check src tests` before submitting.
4. Update `CHANGELOG.md` for user-visible changes.
5. Describe the physical/algorithmic motivation, not only the code change.

## Code style

- Python 3.9+, `snake_case` functions, `PascalCase` classes.
- Type hints for public functions.
- English identifiers; Chinese comments are acceptable in domain-specific code.
- No new heavy dependencies without discussion; NumPy + Pillow are the baseline.

## Reporting accuracy issues

Please include:

- input frame size and frame rate,
- the frame number,
- whether the frame is `measured` or `inertia`,
- a cropped image with the expected edge marked,
- the parameters used.

This makes it possible to separate a detector issue from an occlusion-model issue.
