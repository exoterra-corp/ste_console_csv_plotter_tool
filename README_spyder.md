# H12 Telemetry Plotting (Spyder / Desktop)

Generate dual-axis plots from H12 test-collection CSV files.

## Files

| File | What it is | Do you edit it? |
|------|------------|-----------------|
| `H12_test_data_plot.py` | The plotting library (all the logic). | Rarely — see "Notes" below. |
| `h12_plot_config_spyder.py` | Your control file: pick the data file and what to plot. | Yes, every time. |

Keep **both files in the same folder**.

## Requirements

- Python 3 with `pandas` and `matplotlib`.
- Anaconda-based Spyder installs normally include both. If a plot run
  complains that one is missing, install it from an Anaconda Prompt:
  `pip install pandas matplotlib`

## Quick start

1. Put `H12_test_data_plot.py` and `h12_plot_config_spyder.py` in one folder.
2. Open `h12_plot_config_spyder.py` in Spyder.
3. Set the two paths near the top:
   - `CSV`     — full path to the data file you want to plot.
   - `OUT_DIR` — folder where the PNG images should be saved.
   On Windows, write paths as a raw string, e.g. `r"C:\Users\you\H12\data.csv"`,
   or with forward slashes, e.g. `"C:/Users/you/H12/data.csv"`.
4. Choose what to plot (see next section).
5. Press **Run** (F5). The PNG file paths are printed in the console, and the
   images appear in `OUT_DIR`.

## Choosing what to plot

The config has a list of every available signal as a named constant, grouped
by type (voltage, current, temperature, pressure). You build two axes from
these:

- `AXIS1` — left axis (cool colors)
- `AXIS2` — right axis (warm colors)

**Rule:** every signal on one axis must share a unit. So you can put several
voltages together on AXIS1, or several currents together on AXIS2, but you
cannot mix (say) a voltage and a temperature on the same axis. Put differing
unit types on opposite axes, or make separate plots.

Example — anode voltage on the left, three currents on the right:

```python
AXIS1 = [ANODE_VOUT]
AXIS2 = [ANODE_IOUT, ANODE_X_SWITCH, ANODE_Y_SWITCH]
```

### Full plots

`FULL` is a list of `(left, right)` pairs. Each pair makes one full-length
plot:

```python
FULL = [
    (AXIS1, AXIS2),
]
```

### Zoom plots

`ZOOMS` is a list of `(left, right, start_sec, end_sec)`. Times are in
**seconds**. Leave it empty (`ZOOMS = []`) for none:

```python
ZOOMS = [
    (AXIS1, AXIS2, 30, 300),     # zoom from 30 s to 300 s
]
```

To zoom to the end of a run, just use a number larger than the run length —
it clips to the available data.

## What the plots look like (fixed in the library)

- X-axis is in **seconds** along the bottom; a second axis on top shows
  elapsed time (`m:ss` for runs under an hour, `h:mm` for longer).
- Tick spacing adapts to run length, so short and multi-hour runs both label
  cleanly.
- Two boxed legends sit above the plot (left-axis signals on the left,
  right-axis on the right) with the title centered between them.
- Title is `H12 Test Collection <filename>`.

## Units and conversions (applied automatically)

| Type | Stored as | Shown as | Axis decimals |
|------|-----------|----------|---------------|
| Voltage | mV | V | 1 |
| Current | mA | A | 1 |
| Temperature | C | C | 1 |
| Tank pressure | psi | psi | integer |
| Other pressure | milli-psi | psi | 1 |

- Sample rate is assumed to be **750 ms per row**.
- Temperature readings below -100 C (sensor dropouts/disconnects) are
  clamped to 0.

## Notes / things to know

- **Temporary voltage fix:** `anode_input_v` and `anode_filtered_v` are
  currently multiplied by 1000 in the library, because they appear to be
  logged in volts rather than millivolts (suspected PPU software bug). Once
  the real telemetry units are confirmed, edit `SIGNAL_SCALE_OVERRIDE` near
  the top of `H12_test_data_plot.py` (remove those two entries if the data is
  fixed at the source).
- **Adding a new signal:** if a future CSV has a new column, add it to
  `SIGNAL_KIND` in the library with its type, and add a matching constant in
  the config.
- **Changing appearance:** figure size (`FIG_WIDTH` / `FIG_HEIGHT`), colors,
  and tick rules are constants near the top of the library.

## Troubleshooting

- *"Unknown signal 'xyz'"* — the column isn't registered; add it to
  `SIGNAL_KIND` in the library.
- *"Signals on one axis must share a unit"* — you mixed types on one axis;
  split them across AXIS1/AXIS2 or into separate plots.
- *Blank/odd image* — check the `CSV` path is correct and points to a real
  file; the console prints the output path on success.
