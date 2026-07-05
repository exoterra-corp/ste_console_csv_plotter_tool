# -*- coding: utf-8 -*-
"""
H12 Plot GUI (with live preview)
================================

A simple point-and-click front end for making H12 telemetry plots. No coding
required. Uses Python's built-in tkinter plus matplotlib/pandas (which the
plotting already needs), so nothing extra to install on a standard Windows
Python or Anaconda/Spyder setup.

Run from Spyder (open this file, press Run / F5) or a command line:

    python h12_plot_gui.py

Requirements:
  - H12_test_data_plot.py must be in the SAME folder as this file.
  - pandas and matplotlib available (Anaconda/Spyder ship with them).

Features:
  1) Pick a CSV file to plot.
  2) Pick a folder to save the images.
  3) Choose Axis 1 / Axis 2 parameters, with smart type locking: once a type
     is chosen for one axis, that axis only allows the same type and the other
     axis blocks that type; clearing an axis frees things up again.
  4) Zoom start/stop in seconds — initialised to the full data range. Edit a
     value and press Enter to apply; "Reset to full" restores the whole range.
  5) LIVE PREVIEW pane (right side) auto-updates as you change things, so you
     can read the time axis and decide what to zoom into before saving.
  6) Print (save) or Cancel (close).
"""

import os
import sys
import traceback

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")  # interactive backend for embedding in tkinter
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Reuse the plotting library so classification/logic never drift out of sync.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import H12_test_data_plot as h12
except Exception as exc:  # pragma: no cover
    _IMPORT_ERROR = exc
    h12 = None
else:
    _IMPORT_ERROR = None

# For very large files, decimate the PREVIEW to stay responsive. Saved output
# is always full resolution.
PREVIEW_MAX_POINTS = 4000
# Wait this long (ms) after the last change before redrawing the preview.
PREVIEW_DEBOUNCE_MS = 400


KIND_LABEL = {
    h12.VOLTAGE if h12 else "voltage": "Voltage (V)",
    h12.CURRENT if h12 else "current": "Current (A)",
    h12.TEMPERATURE if h12 else "temp": "Temperature (C)",
    h12.TANK_PRESSURE if h12 else "tank_pressure": "Tank pressure (psi)",
    h12.PRESSURE if h12 else "pressure": "Pressure (psi)",
}


class AxisSelector(ttk.LabelFrame):
    """A labelled group of checkbuttons for one axis, with type awareness."""

    def __init__(self, master, title, signals_by_kind, on_change):
        super().__init__(master, text=title, padding=6)
        self._on_change = on_change
        self._vars = {}
        self._checks = {}
        self._kind_of = {}
        self._blocked_kinds = set()

        row = 0
        for kind, signals in signals_by_kind:
            ttk.Label(self, text=KIND_LABEL.get(kind, kind),
                      font=("TkDefaultFont", 9, "bold")).grid(
                row=row, column=0, sticky="w", pady=(4, 0))
            row += 1
            for sig in signals:
                var = tk.BooleanVar(value=False)
                chk = ttk.Checkbutton(self, text=sig, variable=var,
                                      command=self._changed)
                chk.grid(row=row, column=0, sticky="w", padx=(12, 0))
                self._vars[sig] = var
                self._checks[sig] = chk
                self._kind_of[sig] = kind
                row += 1

    def selected(self):
        return [s for s, v in self._vars.items() if v.get()]

    def selected_kind(self):
        sel = self.selected()
        return self._kind_of[sel[0]] if sel else None

    def clear(self):
        for v in self._vars.values():
            v.set(False)
        self._changed()

    def set_blocked_kinds(self, kinds):
        self._blocked_kinds = set(kinds)
        self._refresh_enabled()

    def _changed(self):
        self._refresh_enabled()
        if self._on_change:
            self._on_change()

    def _refresh_enabled(self):
        own_kind = self.selected_kind()
        for sig, chk in self._checks.items():
            kind = self._kind_of[sig]
            if self._vars[sig].get():
                state = "normal"
            elif kind in self._blocked_kinds:
                state = "disabled"
            elif own_kind is not None and kind != own_kind:
                state = "disabled"
            else:
                state = "normal"
            chk.configure(state=state)


class App(ttk.Frame):
    # Preview figure size in inches — wide and short to match the pane shape.
    PREVIEW_W_IN = 7.0
    PREVIEW_H_IN = 4.6

    def __init__(self, master):
        super().__init__(master, padding=10)
        self.grid(sticky="nsew")
        master.title("H12 Plot Generator")

        self.csv_path = tk.StringVar()
        self.out_dir = tk.StringVar()
        self.zoom_start = tk.StringVar()
        self.zoom_stop = tk.StringVar()
        self.chart_title = tk.StringVar()

        self._df = None            # cached DataFrame for the loaded CSV
        self._df_path = None       # which path _df belongs to
        self._preview_job = None   # pending debounce callback id
        self._t_min = 0            # data start time (s)
        self._t_max = 0            # data end time (s)
        # Last-accepted zoom field values, for reverting invalid entries.
        self._last_start = ""
        self._last_stop = ""
        # Whether the user has typed their own title (so we don't overwrite it
        # when a new CSV is loaded).
        self._title_customized = False
        self._suppress_title_trace = False

        controls = ttk.Frame(self)
        controls.grid(row=0, column=0, sticky="nsew")
        self._build_controls(controls)
        self._build_preview(self)

        # Let the preview column (1) expand and take extra space; keep the
        # controls column (0) at its natural width.
        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        # Live-refresh only on CSV change; zoom fields update on Enter only.
        self.csv_path.trace_add("write", lambda *_: self._on_csv_changed())
        # Title edits refresh the preview live and mark it as user-customized.
        self.chart_title.trace_add("write", lambda *_: self._on_title_changed())

        self._sync_axes()
        # Defer the first preview until the window has been fully laid out, so
        # the canvas has its real size and the plot isn't cut off on first draw.
        self.after_idle(self._schedule_preview)

    def _build_controls(self, parent):
        frm = ttk.Frame(parent)
        frm.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        frm.columnconfigure(1, weight=1)
        ttk.Label(frm, text="CSV file:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.csv_path, width=30).grid(
            row=0, column=1, sticky="ew", padx=6)
        ttk.Button(frm, text="Browse...", command=self._pick_csv).grid(
            row=0, column=2)
        ttk.Label(frm, text="Save to:").grid(
            row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(frm, textvariable=self.out_dir, width=30).grid(
            row=1, column=1, sticky="ew", padx=6, pady=(4, 0))
        ttk.Button(frm, text="Browse...", command=self._pick_dir).grid(
            row=1, column=2, pady=(4, 0))

        groups = self._signals_by_kind()
        axes = ttk.Frame(parent)
        axes.grid(row=1, column=0, sticky="nsew")
        self.axis1 = AxisSelector(axes, "Axis 1 (left)", groups,
                                  self._on_axis_change)
        self.axis1.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.axis2 = AxisSelector(axes, "Axis 2 (right)", groups,
                                  self._on_axis_change)
        self.axis2.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        clr = ttk.Frame(parent)
        clr.grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Button(clr, text="Clear Axis 1", command=self.axis1.clear).grid(
            row=0, column=0, padx=(0, 6))
        ttk.Button(clr, text="Clear Axis 2", command=self.axis2.clear).grid(
            row=0, column=1)

        zoom = ttk.LabelFrame(parent, text="Zoom", padding=6)
        zoom.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(zoom, text="Start (s):").grid(row=0, column=0, sticky="w")
        e_start = ttk.Entry(zoom, textvariable=self.zoom_start, width=9)
        e_start.grid(row=0, column=1, padx=(4, 12))
        ttk.Label(zoom, text="Stop (s):").grid(row=0, column=2, sticky="w")
        e_stop = ttk.Entry(zoom, textvariable=self.zoom_stop, width=9)
        e_stop.grid(row=0, column=3, padx=(4, 8))
        ttk.Button(zoom, text="Reset to full",
                   command=self._reset_zoom).grid(row=0, column=4)
        ttk.Label(zoom, text="Press Enter to apply times.").grid(
            row=1, column=0, columnspan=5, sticky="w", pady=(2, 0))
        # Apply on Enter only (not per keystroke).
        e_start.bind("<Return>", lambda _e: self._apply_zoom())
        e_stop.bind("<Return>", lambda _e: self._apply_zoom())

        # Chart title (editable; prefilled with the default when a CSV loads).
        title_frm = ttk.Frame(parent)
        title_frm.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        title_frm.columnconfigure(1, weight=1)
        ttk.Label(title_frm, text="Chart Title:").grid(
            row=0, column=0, sticky="w")
        ttk.Entry(title_frm, textvariable=self.chart_title).grid(
            row=0, column=1, sticky="ew", padx=(6, 0))

        btns = ttk.Frame(parent)
        btns.grid(row=5, column=0, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Print", command=self._print).grid(
            row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Cancel", command=self.master.destroy).grid(
            row=0, column=1)

    def _build_preview(self, parent):
        frm = ttk.LabelFrame(parent, text="Preview", padding=6)
        frm.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        # Canvas fills the frame; status line sits under it.
        frm.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)
        self._preview_frame = frm
        self._fig = plt.figure(figsize=(self.PREVIEW_W_IN, self.PREVIEW_H_IN),
                               dpi=100)
        self._canvas = FigureCanvasTkAgg(self._fig, master=frm)
        self._canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._status = ttk.Label(frm, text="", foreground="#555")
        self._status.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self._show_message("Select a CSV and signals to preview.")

    def _signals_by_kind(self):
        order = [h12.VOLTAGE, h12.CURRENT, h12.TEMPERATURE,
                 h12.TANK_PRESSURE, h12.PRESSURE]
        grouped = []
        for kind in order:
            sigs = [s for s, k in h12.SIGNAL_KIND.items() if k == kind]
            if sigs:
                grouped.append((kind, sigs))
        return grouped

    def _on_axis_change(self):
        self._sync_axes()
        self._schedule_preview()

    def _sync_axes(self):
        k1 = self.axis1.selected_kind()
        k2 = self.axis2.selected_kind()
        self.axis1.set_blocked_kinds({k2} if k2 else set())
        self.axis2.set_blocked_kinds({k1} if k1 else set())

    def _zoom_values(self):
        """Return (start, stop) integer seconds from the fields, or None if the
        fields represent the full range. Assumes fields hold valid ints (they
        are validated on Enter)."""
        zs, zt = self.zoom_start.get().strip(), self.zoom_stop.get().strip()
        if not zs or not zt:
            return None
        try:
            start, stop = int(float(zs)), int(float(zt))
        except ValueError:
            return None
        # Full range -> treat as a full plot (no zoom).
        if start <= self._t_min and stop >= self._t_max:
            return None
        return start, stop

    def _apply_zoom(self):
        """Validate and apply the zoom fields (called on Enter).

        Rules (times are whole seconds, valid range is 0 .. last data point):
          - A value outside [0, t_max], or unparseable -> ignore the change and
            revert BOTH fields to their previous accepted values.
          - start > stop  -> the user pushed start past the end: set stop to the
            last data point.
          - stop  < start -> the user pulled stop below the start: set start to
            the first data point.
        """
        lo, hi = self._t_min, self._t_max
        zs, zt = self.zoom_start.get().strip(), self.zoom_stop.get().strip()

        try:
            start, stop = int(float(zs)), int(float(zt))
        except ValueError:
            self._revert_zoom()
            return

        # Out-of-bounds -> ignore, revert to previous values.
        if start < lo or start > hi or stop < lo or stop > hi:
            self._revert_zoom()
            return

        # Cross-over handling. Figure out which field the user just changed by
        # comparing against the previous accepted values.
        prev_start, prev_stop = self._last_start_val(), self._last_stop_val()
        if start > stop:
            if start != prev_start:      # start was moved past stop
                stop = hi
            else:                        # stop was moved below start
                start = lo

        self.zoom_start.set(str(start))
        self.zoom_stop.set(str(stop))
        self._last_start, self._last_stop = str(start), str(stop)
        self._schedule_preview()

    def _revert_zoom(self):
        self.zoom_start.set(self._last_start)
        self.zoom_stop.set(self._last_stop)

    def _last_start_val(self):
        try:
            return int(float(self._last_start))
        except (ValueError, TypeError):
            return self._t_min

    def _last_stop_val(self):
        try:
            return int(float(self._last_stop))
        except (ValueError, TypeError):
            return self._t_max

    def _reset_zoom(self):
        """Reset the zoom fields to the full data range."""
        self.zoom_start.set(str(self._t_min))
        self.zoom_stop.set(str(self._t_max))
        self._last_start, self._last_stop = str(self._t_min), str(self._t_max)
        self._schedule_preview()

    def _on_csv_changed(self):
        """When the CSV changes, load it, set time bounds, init the zoom fields
        to the full range, and prefill the default title (unless the user has
        typed their own)."""
        csv = self.csv_path.get().strip()
        if csv and os.path.isfile(csv):
            try:
                self._load_df(csv)  # sets _t_min/_t_max
                if not self._title_customized:
                    self._set_default_title(csv)
                self._reset_zoom()
                return
            except Exception:
                pass
        self._schedule_preview()

    def _set_default_title(self, csv):
        """Set the title box to the default without marking it customized."""
        self._suppress_title_trace = True
        self.chart_title.set(h12.default_title(csv))
        self._suppress_title_trace = False

    def _on_title_changed(self):
        # Programmatic prefill sets _suppress_title_trace so it isn't counted
        # as a user edit.
        if getattr(self, "_suppress_title_trace", False):
            return
        self._title_customized = True
        self._schedule_preview()

    def _pick_csv(self):
        path = filedialog.askopenfilename(
            title="Select a CSV data file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self.csv_path.set(path)
            if not self.out_dir.get():
                self.out_dir.set(os.path.dirname(path))

    def _pick_dir(self):
        path = filedialog.askdirectory(title="Select a folder to save plots")
        if path:
            self.out_dir.set(path)

    def _load_df(self, csv):
        if self._df_path != csv:
            self._df = h12.pd.read_csv(h12._resolve_csv(csv))
            self._df_path = csv
            # Compute the data time bounds (seconds) from the sample column.
            t = h12._time_seconds(self._df)
            self._t_min = int(max(0, round(float(t.min()))))
            self._t_max = int(round(float(t.max())))
        return self._df

    def _schedule_preview(self):
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(PREVIEW_DEBOUNCE_MS, self._refresh_preview)

    def _show_message(self, text):
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        ax.axis("off")
        ax.text(0.5, 0.5, text, ha="center", va="center", wrap=True,
                fontsize=10, color="#666")
        self._canvas.draw_idle()

    def _refresh_preview(self):
        self._preview_job = None
        csv = self.csv_path.get().strip()
        a1, a2 = self.axis1.selected(), self.axis2.selected()

        if not csv or not os.path.isfile(csv):
            self._show_message("Choose a valid CSV file to preview.")
            self._status.configure(text="")
            return
        if not a1 or not a2:
            self._show_message("Select at least one signal on each axis.")
            self._status.configure(text="")
            return
        try:
            zoom = self._zoom_values()
        except ValueError as e:
            self._show_message(str(e))
            self._status.configure(text="")
            return

        try:
            df = self._load_df(csv)
            start, stop = (zoom if zoom else (None, None))
            # Draw into the persistent canvas figure (reuse, don't swap) so the
            # canvas always shows the latest plot and every change refreshes.
            h12.build_figure(csv, a1, a2, start, stop,
                             df=df, max_points=PREVIEW_MAX_POINTS,
                             target_fig=self._fig,
                             title=self.chart_title.get().strip() or None)
        except Exception as e:
            self._show_message(f"Preview error:\n{e}")
            self._status.configure(text="")
            return

        self._canvas.draw_idle()

        n = len(df)
        kind = "zoom" if zoom else "full"
        note = f"Previewing {kind} plot."
        if n > PREVIEW_MAX_POINTS:
            note += "  (downsampled for speed; saved file is full resolution)"
        self._status.configure(text=note)

    def _print(self):
        csv = self.csv_path.get().strip()
        out = self.out_dir.get().strip() or None
        a1, a2 = self.axis1.selected(), self.axis2.selected()

        if not csv or not os.path.isfile(csv):
            messagebox.showerror("Missing CSV",
                                 "Please choose a valid CSV file.")
            return
        if not a1 or not a2:
            messagebox.showerror(
                "Missing signals",
                "Please select at least one parameter on each axis.")
            return
        try:
            zoom = self._zoom_values()
        except ValueError as e:
            messagebox.showerror("Zoom times", str(e))
            return

        try:
            ttl = self.chart_title.get().strip() or None
            made = [h12.plot_full(csv, a1, a2, out, title=ttl)]
            if zoom:
                made.append(h12.plot_zoom(csv, a1, a2, zoom[0], zoom[1], out,
                                          title=ttl))
        except Exception as exc:
            messagebox.showerror(
                "Plotting error",
                f"Something went wrong:\n\n{exc}\n\n{traceback.format_exc()}")
            return

        messagebox.showinfo(
            "Done",
            "Saved:\n\n" + "\n".join(os.path.basename(p) for p in made) +
            f"\n\nin:\n{out or os.getcwd()}")


def main():
    root = tk.Tk()
    if _IMPORT_ERROR is not None:
        root.withdraw()
        messagebox.showerror(
            "Cannot load plotting library",
            "Could not import H12_test_data_plot.py.\n"
            "Make sure it is in the same folder as this GUI.\n\n"
            f"{_IMPORT_ERROR}")
        root.destroy()
        return
    App(root)
    root.minsize(1050, 640)
    root.mainloop()


if __name__ == "__main__":
    main()
