# H12 Telemetry Plotter (GUI)

The H12 Telemetry Plotter is a tool for making dual-axis plots from H12 test-collection CSV files exported from the STE Console.

## Files you need

Keep these two files **in the same folder**:

| File | What it is |
|------|------------|
| `h12_plot_gui.py` | The application you run. |
| `H12_test_data_plot.py` | The plotting engine it uses. Don't need to open it. |

## Requirements

- Python 3 with `pandas` and `matplotlib`. Anaconda / Spyder installs include
  all of these, plus `tkinter` (the window toolkit), by default.
- Nothing else to install.

## Starting the tool

**From Spyder:** open `h12_plot_gui.py` and press Run (F5).

**From a command line:** in the folder containing the two files, run
`python h12_plot_gui.py`. On a machine where Python came with Anaconda, use the
**Anaconda Prompt** (search the Start menu) rather than the plain Command
Prompt, so it can find Python.

A window titled "H12 Plot Generator" opens.

## Using it

1. **CSV file** — click Browse and pick the data file to plot.
2. **Save to** — click Browse and pick the folder where saved images should go
   (it defaults to the CSV's folder).
3. **Axis 1 (left)** and **Axis 2 (right)** — tick the signals you want on each
   axis. Colors: Axis 1 uses a cool palette, Axis 2 a warm palette.
4. **Zoom** — optionally narrow the time window (see below).
5. **Preview** — the plot on the right updates automatically as you make
   changes, so you can see exactly what you'll get.
6. **Print** — saves the plot(s) as PNG image(s) to your chosen folder. If a
   zoom window is set, both a full-range plot and a zoomed plot are saved.
7. **Cancel** — closes the tool.

### Smart axis selection

Each axis can hold several signals, but they must all be the **same type**
(e.g. several voltages together). The tool enforces this for you:

- As soon as you tick a signal on an axis, that axis locks to its type and the
  other types grey out on that axis.
- The opposite axis blocks that type, so you can't put the same type on both.
- Use **Clear Axis 1** / **Clear Axis 2** to empty an axis and free the types
  up again.

Example: tick two voltages on Axis 1 and two currents on Axis 2 to plot voltage
vs. current.

### Zoom

The Start and Stop boxes hold times in **whole seconds**. When you load a CSV
they fill in automatically with the full time range, so the preview always
shows the whole run to begin with.

- Type a new value and press **Enter** to apply it (typing alone does nothing
  until you press Enter).
- If you set Start past Stop, Stop jumps to the last data point.
- If you set Stop below Start, Start drops to the first data point.
- A value outside the data's time range (or not a number) is ignored and the
  box snaps back to its previous value.
- **Reset to full** restores the whole time range.

When Start/Stop cover the full range, Print saves just the full plot. When they
cover a narrower window, Print also saves a zoomed plot of that window.

## What the plots look like

- X-axis is in **seconds** along the bottom, with an elapsed-time scale
  (`m:ss` for short runs, `h:mm` for long ones) along the top.
- Tick spacing adjusts to the run length automatically.
- Two boxed legends sit above the plot with the title centered between them.
- The title is `H12 Test Collection <filename>`.

## Units (applied automatically)

| Type | In the CSV | Shown as | Axis decimals |
|------|-----------|----------|---------------|
| Voltage | mV | V | 1 |
| Current | mA | A | 1 |
| Temperature | C | C | 1 |
| Tank pressure | psi | psi | whole number |
| Other pressure | milli-psi | psi | 1 |

- Sample rate is assumed to be **750 ms per row**.
- Temperature readings below -100 C (sensor dropouts) are shown as 0.

## Things to know

- **Temporary voltage fix:** `anode_input_v` and `anode_filtered_v` are
  currently multiplied by 1000 inside `H12_test_data_plot.py`, because they
  appear to be logged in volts rather than millivolts (a suspected data/units
  issue in the source software). Once the real units are confirmed, this should
  be removed — see `SIGNAL_SCALE_OVERRIDE` near the top of that file.
- **Large files:** the on-screen preview is downsampled for speed on long
  recordings. Saved (Printed) images are always full resolution.

## Troubleshooting

- **"Cannot load plotting library"** — the two files aren't in the same folder.
  Put `H12_test_data_plot.py` next to `h12_plot_gui.py`.
- **Preview says "Select at least one signal on each axis"** — you need at
  least one ticked signal on both Axis 1 and Axis 2.
- **A signal I want is greyed out** — another type is selected on that axis (or
  the same type is in use on the other axis). Clear the axis to start over.
- **Nothing happens when I type a zoom time** — press Enter to apply it.
