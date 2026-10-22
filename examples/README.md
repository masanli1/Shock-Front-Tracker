# Examples

## Synthetic demo

No experimental data is required.

```bash
python examples/synthetic_demo.py
```

This will:

1. generate a synthetic sequence with a dim fireball and two expanding side arcs,
2. run the tracker,
3. refresh `docs/assets/demo.gif`, `demo_contact_sheet.png`, `demo_curves.png`.

To keep the generated frames:

```bash
python examples/make_synthetic.py --output examples/synthetic --frames 16
shockfront track \
    --input examples/synthetic \
    --output examples/synthetic_results \
    --fps 1000 \
    --bright-threshold 100 \
    --sal-threshold 5 \
    --bar-clearance 15 \
    --min-measured-rows 40
```

The synthetic frames are intentionally simple: they test the row-wise scan,
column suppression, measured/inertia labelling and output generation, not the
physics of a real explosion.
