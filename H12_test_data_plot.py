#!/usr/bin/env python3
"""
H12 test data plotting library.

This module knows *how* to draw dual-axis plots from an H12 test-collection
CSV: it handles unit conversion, axis formatting, the seconds x-axis with
15-minute / hourly ticks, and optional zoom windows. It does NOT contain
dataset specifics -- each dataset supplies its own small config that calls
plot_full() and/or plot_zoom().

Data structure is fixed across all test rounds; only the values change.

------------------------------------------------------------------------
Signal classification and display rules
------------------------------------------------------------------------
Voltage     : stored in mV, displayed in V, 3 decimal places
Current     : stored in mA, displayed in A, 3 decimal places
Temperature : stored in Celsius, displayed in C, 1 decimal place
Tank press. : stored in psi, displayed in psi, integer
Other press.: stored in milli-psi, displayed in psi, 3 decimal places

Sample rate is 750 ms per row; the x-axis is always shown in seconds.
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FuncFormatter
from matplotlib import cm
import numpy as np

# ----- Fixed acquisition / appearance constants -----------------------------
SECONDS_PER_SAMPLE = 0.75       # one CSV row == 750 ms
FIG_WIDTH = 14                  # figure width in inches
FIG_HEIGHT = 9                  # figure height in inches (taller -> taller plot)
MINOR_TICK_MIN = 15             # minor x ticks every 15 minutes
MAJOR_TICK_MIN = 60             # major x ticks every 60 minutes (1 hour)
LEFT_COLOR  = "#1f5fbf"         # blue  -> left axis
RIGHT_COLOR = "#d1483f"         # red   -> right axis
TITLE_PREFIX = "H12 Test Collection"

# Colormaps used to derive colors when multiple signals share an axis.
# Left axis -> cool multi-hue family, right axis -> warm multi-hue family.
# A single signal on an axis uses the solid anchor color (LEFT/RIGHT_COLOR).
LEFT_CMAP = "winter"    # blue -> green progression (cool)
RIGHT_CMAP = "autumn"   # red -> yellow progression (warm)

# ----- Signal classification (column name -> kind) --------------------------
# kind drives unit conversion, axis label, and number formatting.
VOLTAGE = "voltage"      # mV -> V, 3 dp
CURRENT = "current"      # mA -> A, 3 dp
TEMPERATURE = "temp"     # C, 1 dp
TANK_PRESSURE = "tank_pressure"    # psi, integer
PRESSURE = "pressure"    # milli-psi -> psi, 3 dp
COUNTS = "counts"        # unitless DAC counts, integer
MASS = "mass"            # mg, 1 dp

SIGNAL_KIND = {
    # Voltages (mV -> V)
    "anode_input_v":    VOLTAGE,
    "anode_filtered_v": VOLTAGE,
    "anode_vout":       VOLTAGE,   # typically 300-500 V
    "keeper_flyback":   VOLTAGE,
    "magnet_vout":      VOLTAGE,
    "cathode_hf_voltage": VOLTAGE,
    # Currents (mA -> A)
    "anode_x_switch":   CURRENT,
    "anode_y_switch":   CURRENT,
    "anode_iout":       CURRENT,
    "keeper_iout":      CURRENT,
    "magnet_iout":      CURRENT,
    # Temperatures (C)
    "temp_thruster":    TEMPERATURE,
    "temp_keeper_mcu":  TEMPERATURE,
    "temp_pds":         TEMPERATURE,
    "temp_anode_mcu":   TEMPERATURE,
    "temp_magnet_mcu":  TEMPERATURE,
    # Pressures
    "pressure_tank":    TANK_PRESSURE,    # psi, integer
    "pressure_anode":   PRESSURE,         # milli-psi -> psi
    "pressure_cathode": PRESSURE,
    "pressure_reg":     PRESSURE,
    # Unitless DAC counts
    "anode_pcv_dac_cnts":   COUNTS,
    "cathode_pcv_dac_cnts": COUNTS,
    # Mass
    "fuel_usage_estimate": MASS,   # mg
}

# Per-kind handling: (scale factor, unit label, axis-tick formatter)
# Note: formatters control only the y-axis tick *labels*. Plotted data keeps
# full precision; voltage/current/pressure are stored to 3 dp but their axis
# ticks are shown to 1 dp for readability.
_KIND_SPEC = {
    VOLTAGE:       (1.0 / 1000.0, "V",   lambda v, _: f"{v:.1f}"),
    CURRENT:       (1.0 / 1000.0, "A",   lambda v, _: f"{v:.1f}"),
    TEMPERATURE:   (1.0,          "C",   lambda v, _: f"{v:.1f}"),
    TANK_PRESSURE: (1.0,          "psi", lambda v, _: f"{int(round(v))}"),
    PRESSURE:      (1.0 / 1000.0, "psi", lambda v, _: f"{v:.1f}"),
    COUNTS:        (1.0,          "counts", lambda v, _: f"{int(round(v))}"),
    MASS:          (1.0,          "mg",  lambda v, _: f"{v:.1f}"),
}

# Per-signal scale overrides (TEMPORARY).
# Normally a voltage's kind scale (mV -> V) is applied. These two signals are
# being logged already in volts by the PPU software (suspected units bug), so
# we multiply by 1000 here to cancel the mV->V division and display the raw
# volt value. Remove these once the telemetry units are confirmed/fixed.
SIGNAL_SCALE_OVERRIDE = {
    "anode_input_v":    1000.0,
    "anode_filtered_v": 1000.0,
}


def _kind_of(col: str) -> str:
    if col not in SIGNAL_KIND:
        raise KeyError(
            f"Unknown signal '{col}'. Add it to SIGNAL_KIND in "
            f"H12_test_data_plot.py with its kind.")
    return SIGNAL_KIND[col]


def _series(df: pd.DataFrame, col: str):
    """Return (converted_values, unit_label, formatter) for a column.

    Temperature readings below -100 C are sensor dropouts / disconnects
    (large negative sentinels) and are clamped to 0.
    """
    kind = _kind_of(col)
    scale, unit, fmt = _KIND_SPEC[kind]
    scale *= SIGNAL_SCALE_OVERRIDE.get(col, 1.0)
    vals = df[col].astype(float)
    if kind == TEMPERATURE:
        vals = vals.mask(vals < -100, 0.0)
    return vals * scale, unit, fmt


def _time_seconds(df: pd.DataFrame):
    if "sample" in df.columns:
        return df["sample"].astype(float) * SECONDS_PER_SAMPLE
    return pd.Series(range(len(df)), dtype=float) * SECONDS_PER_SAMPLE


def _hms(seconds: float) -> str:
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}:{m:02d}"


def _mmss(seconds: float) -> str:
    seconds = int(round(seconds))
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"


def _title_stub(csv_path: str) -> str:
    return os.path.splitext(os.path.basename(csv_path))[0]


def default_title(csv_path):
    """The default chart title for a given CSV (used to prefill the GUI box)."""
    return f"{TITLE_PREFIX} {_title_stub(_resolve_csv(csv_path))}"


def _as_list(signals):
    """Accept a bare column name or a list; always return a list."""
    if isinstance(signals, str):
        return [signals]
    return list(signals)


def _check_same_unit(signals):
    """Ensure all signals on one axis share a unit; return (unit, formatter)."""
    units = {_KIND_SPEC[_kind_of(s)][1] for s in signals}
    if len(units) > 1:
        raise ValueError(
            f"Signals on one axis must share a unit; got {sorted(units)} "
            f"for {signals}. Put differing unit types on opposite axes "
            f"or on separate plots.")
    # formatter/unit come from the (shared) kind of the first signal
    _, unit, fmt = _KIND_SPEC[_kind_of(signals[0])]
    return unit, fmt


def _shades(cmap_name, n):
    """Return n distinguishable colors spanning a sequential colormap.

    Used when n >= 2 (a single signal uses the solid anchor color). Sampling
    the full 0..1 range gives the multi-hue progression (e.g. red->yellow).
    """
    cmap = cm.get_cmap(cmap_name)
    if n == 1:
        return [cmap(0.0)]
    return [cmap(x) for x in np.linspace(0.0, 1.0, n)]


def _draw(df, csv_path, left, right, t_lo, t_hi, zoom_label, is_zoom=False,
          fig_width=None, fig_height=None, target_fig=None, title=None):
    """Core dual-axis drawing routine shared by full and zoom plots.

    left, right : a column name or list of column names. All signals on a
    given side must share a unit (e.g. several voltages on the left).
    fig_width/fig_height : optional inches; default to the export size. The
    preview passes a smaller, wider size so it fits its pane.
    target_fig : if given, clear and draw into this existing Figure instead of
    creating a new one. The GUI reuses its canvas figure this way, which avoids
    fragile figure-swapping on the Tk canvas.
    """
    fig_width = FIG_WIDTH if fig_width is None else fig_width
    fig_height = FIG_HEIGHT if fig_height is None else fig_height
    t = _time_seconds(df)

    left = _as_list(left)
    right = _as_list(right)
    left_unit, left_fmt = _check_same_unit(left)
    right_unit, right_fmt = _check_same_unit(right)

    left_colors = ([LEFT_COLOR] if len(left) == 1
                   else _shades(LEFT_CMAP, len(left)))
    right_colors = ([RIGHT_COLOR] if len(right) == 1
                    else _shades(RIGHT_CMAP, len(right)))

    if target_fig is not None:
        fig = target_fig
        fig.clear()
        ax_l = fig.add_subplot(111)
    else:
        fig, ax_l = plt.subplots(figsize=(fig_width, fig_height))

    # Scale fonts/spacing for smaller (preview) figures so the legend band and
    # title don't overwhelm a short figure. 1.0 at the default export height.
    # Use the figure's real height (matters when drawing into a reused figure).
    real_h = fig.get_size_inches()[1]
    fig_height = real_h
    scale = min(1.0, real_h / FIG_HEIGHT)
    fs_legend = max(6, 9 * scale)
    fs_label = max(6, 9 * scale)
    fs_title = max(8, 13 * scale)

    for sig, col in zip(left, left_colors):
        vals, _, _ = _series(df, sig)
        ax_l.plot(t, vals, color=col, linewidth=0.9, label=f"{sig} ({left_unit})")
    ax_l.set_xlabel("Time (s)")
    ax_l.set_ylabel(f"({left_unit})", color=LEFT_COLOR)
    ax_l.tick_params(axis="y", labelcolor=LEFT_COLOR)
    ax_l.yaxis.set_major_formatter(FuncFormatter(left_fmt))

    ax_r = ax_l.twinx()
    for sig, col in zip(right, right_colors):
        vals, _, _ = _series(df, sig)
        ax_r.plot(t, vals, color=col, linewidth=0.9, label=f"{sig} ({right_unit})")
    ax_r.set_ylabel(f"({right_unit})", color=RIGHT_COLOR)
    ax_r.tick_params(axis="y", labelcolor=RIGHT_COLOR)
    ax_r.yaxis.set_major_formatter(FuncFormatter(right_fmt))

    # X limits: full range or zoom window (seconds)
    if t_lo is None:
        t_lo = t.min()
    if t_hi is None:
        t_hi = t.max()
    ax_l.set_xlim(t_lo, t_hi)

    span = t_hi - t_lo
    # Choose a "nice" major tick spacing (seconds) that yields roughly 6-12
    # labeled ticks across the visible span, for any run length from a few
    # seconds to several hours. Minor ticks subdivide the major interval.
    nice_steps = (
        5, 10, 15, 30,            # seconds
        60, 120, 300, 600, 900,   # 1, 2, 5, 10, 15 min
        1800, 3600, 7200, 10800,  # 30 min, 1, 2, 3 h
    )
    major = nice_steps[-1]
    for step in nice_steps:
        if span / step <= 12:
            major = step
            break
    minor = major / (4 if major >= 3600 else 2)
    ax_l.xaxis.set_major_locator(MultipleLocator(major))
    ax_l.xaxis.set_minor_locator(MultipleLocator(minor))
    top_major = major

    ax_l.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(x)}"))
    ax_l.tick_params(axis="x", which="minor", length=4)
    ax_l.tick_params(axis="x", which="major", length=8)

    ax_top = ax_l.secondary_xaxis("top")
    ax_top.xaxis.set_major_locator(MultipleLocator(top_major))
    ax_top.xaxis.set_minor_locator(MultipleLocator(top_major / 4))
    # Use m:ss for spans under an hour (full or zoom), h:mm for longer runs.
    if is_zoom or span < 3600:
        ax_top.xaxis.set_major_formatter(FuncFormatter(lambda x, _: _mmss(x)))
        _top_label = "Elapsed time (m:ss)"
    else:
        ax_top.xaxis.set_major_formatter(FuncFormatter(lambda x, _: _hms(x)))
        _top_label = "Elapsed time (h:mm)"
    # Annotate the top axis inline at the right end so it does not collide
    # with the legends stacked above the plot.
    ax_top.set_xlabel("")

    ax_l.grid(True, which="major", axis="both", alpha=0.3)
    ax_l.grid(True, which="minor", axis="x", alpha=0.15)

    # ---- Header band above the plot: three stacked, non-overlapping levels --
    # (from just above the plot upward): elapsed-time label, then the two
    # legend boxes, then the centered title at the very top.
    left_lines = ax_l.get_lines()
    right_lines = ax_r.get_lines()
    n_rows = max(len(left_lines), len(right_lines))

    # Reserve headroom (inches) for label + legends + title. Scaled for small
    # preview figures. Extra room per legend row keeps the title clear.
    header_in = (1.9 + 0.30 * n_rows) * scale
    top = 1.0 - header_in / fig_height
    # Explicit margins so the plot fills the figure (avoids large white bands,
    # especially in the GUI preview where the figure matches the canvas size).
    left_m = min(0.10, 0.9 / fig_width)
    right_m = 1.0 - min(0.10, 0.9 / fig_width)
    bottom_m = min(0.12, 0.8 / fig_height)
    fig.subplots_adjust(top=top, bottom=bottom_m, left=left_m, right=right_m)

    # Vertical positions in axes-fraction coords (1.0 == top of plot). Convert
    # a desired inch offset above the plot into axes fraction.
    plot_in = fig_height * top
    def _frac(inches_above):
        return 1.0 + inches_above / plot_in

    label_y = _frac(0.10 * scale)                     # elapsed-time label
    legend_y = _frac(0.35 * scale)                    # bottom of legend boxes
    # Title sits above the tallest legend box. Each legend row is ~0.22" tall.
    title_y = _frac((0.55 + 0.24 * n_rows) * scale)

    # Elapsed-time scale label, placed at the right edge just above the top
    # ticks so it never overlaps a tick label.
    ax_l.text(1.0, label_y, _top_label, transform=ax_l.transAxes,
              ha="right", va="bottom", fontsize=fs_label, color="0.3")

    # Two vertically-stacked legend boxes: left-axis at top-left, right-axis at
    # top-right.
    ax_l.legend(left_lines, [ln.get_label() for ln in left_lines],
                loc="lower left", bbox_to_anchor=(0.0, legend_y),
                borderaxespad=0.0, fontsize=fs_legend, ncol=1, frameon=True)
    ax_r.legend(right_lines, [ln.get_label() for ln in right_lines],
                loc="lower right", bbox_to_anchor=(1.0, legend_y),
                borderaxespad=0.0, fontsize=fs_legend, ncol=1, frameon=True)

    # Title centered horizontally, above the legend boxes. Use the caller's
    # custom title if given, otherwise the default; the zoom window suffix is
    # always appended so zoom plots stay identifiable.
    base = title if title else f"{TITLE_PREFIX} {_title_stub(csv_path)}"
    full_title = base
    if zoom_label:
        full_title += f"  [{zoom_label}]"
    ax_l.text(0.5, title_y, full_title, transform=ax_l.transAxes,
              ha="center", va="center", fontsize=fs_title, fontweight="bold")

    return fig


def _data_dir():
    """Folder for resolving bare CSV names and default output location.

    Uses the H12_DATA_DIR env var if set (used by the Docker container),
    otherwise the current working directory. Absolute paths bypass this.
    """
    return os.environ.get("H12_DATA_DIR", os.getcwd())


def _resolve_csv(csv_path):
    """Resolve a CSV path: absolute/existing paths are used as-is; bare
    filenames are looked up inside the data dir."""
    if os.path.isabs(csv_path) or os.path.exists(csv_path):
        return csv_path
    return os.path.join(_data_dir(), csv_path)


def _out_path(csv_path, left, right, suffix, out_dir):
    stub = _title_stub(csv_path)
    left_name = "+".join(_as_list(left))
    right_name = "+".join(_as_list(right))
    name = f"{stub}_{left_name}_vs_{right_name}{suffix}.png"
    return os.path.join(out_dir or _data_dir(), name)


def build_figure(csv_path, left, right, start_sec=None, end_sec=None,
                 df=None, max_points=None, fig_width=None, fig_height=None,
                 target_fig=None, title=None):
    """Build and return a matplotlib Figure WITHOUT saving it.

    Shared drawing path for both the saved plots and the live GUI preview, so
    the preview looks exactly like the output (same ticks, legends, styling).

    csv_path        : path to the data file (used for the title and resolution)
    left, right     : signal name or list of names for each axis
    start_sec/end_sec : if both given, produce a zoom over that window
    df              : optional pre-loaded DataFrame (lets the GUI cache the CSV
                      and avoid re-reading it on every preview refresh)
    max_points      : optional cap; if the (visible) data has more rows than
                      this, it is decimated for a faster preview. The saved
                      output never passes this, so files stay full-resolution.
    fig_width/fig_height : optional figure size in inches. The preview passes a
                      smaller size to fit its pane; saved plots use the default.
    title           : optional custom chart title. If omitted, the default
                      "H12 Test Collection <filename>" is used. A zoom window
                      suffix is always appended for zoom plots.

    The caller is responsible for closing the figure (plt.close(fig)).
    """
    csv_path = _resolve_csv(csv_path)
    if df is None:
        df = pd.read_csv(csv_path)

    is_zoom = start_sec is not None and end_sec is not None
    if is_zoom:
        t_lo, t_hi = float(start_sec), float(end_sec)
        label = f"{int(start_sec)}-{int(end_sec)} s"
    else:
        t_lo = t_hi = None
        label = None

    # Optional decimation for a responsive preview on large files.
    if max_points is not None and len(df) > max_points:
        if is_zoom:
            # Decimate only within the visible window so the zoom keeps detail.
            t = _time_seconds(df)
            mask = (t >= t_lo) & (t <= t_hi)
            visible = df[mask]
            if len(visible) > max_points:
                step = int(len(visible) / max_points) + 1
                df = visible.iloc[::step]
            else:
                df = visible
        else:
            step = int(len(df) / max_points) + 1
            df = df.iloc[::step]

    return _draw(df, csv_path, left, right, t_lo, t_hi,
                 zoom_label=label, is_zoom=is_zoom,
                 fig_width=fig_width, fig_height=fig_height,
                 target_fig=target_fig, title=title)


def plot_full(csv_path, left, right, out_dir=None, title=None):
    """Full-length dual-axis plot.

    left, right : a column name or list of column names. All signals on one
    side must share a unit (e.g. two voltages left, one current right).
    title : optional custom chart title.
    """
    csv_path = _resolve_csv(csv_path)
    fig = build_figure(csv_path, left, right, title=title)
    out = _out_path(csv_path, left, right, "", out_dir)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_zoom(csv_path, left, right, start_sec, end_sec, out_dir=None,
              title=None):
    """Zoomed dual-axis plot between start_sec and end_sec (seconds).

    The x-axis reads in seconds; the top axis shows m:ss.
    title : optional custom chart title (the zoom window suffix is appended).
    """
    csv_path = _resolve_csv(csv_path)
    fig = build_figure(csv_path, left, right, start_sec, end_sec, title=title)
    suffix = f"_zoom_{int(start_sec)}-{int(end_sec)}s"
    out = _out_path(csv_path, left, right, suffix, out_dir)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
