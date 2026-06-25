# -*- coding: utf-8 -*-
"""
H12 plot config - SPYDER / desktop version.

How to use in Spyder:
  1. Put this file and H12_test_data_plot.py in the SAME folder.
  2. Set CSV to the full path of your data file (see Windows examples below).
  3. Set OUT_DIR to the folder where you want the PNG images saved.
  4. Edit AXIS1 / AXIS2 / FULL / ZOOMS to choose what to plot.
  5. Open this file in Spyder and press Run (F5).

You need pandas and matplotlib installed (Anaconda/Spyder usually has both).

Rules baked into the library (H12_test_data_plot.py):
  - All signals on one axis must share a unit (e.g. several voltages together).
    Put differing unit types on opposite axes or on separate plots.
  - Voltages: stored mV, shown V (axis ticks 1 dp)
  - Currents: stored mA, shown A (axis ticks 1 dp)
  - Temperatures: stored/shown C (1 dp); readings < -100 C clamped to 0
  - Tank pressure: stored/shown psi (integer)
  - Other pressure: stored milli-psi, shown psi (axis ticks 1 dp)
  - Sample rate 750 ms/row; x-axis in seconds, zoom windows in seconds.
  - NOTE: anode_input_v / anode_filtered_v currently have a TEMPORARY x1000
    scale override in the library (suspected PPU units bug). Remove it there
    once telemetry units are confirmed.
"""

from H12_test_data_plot import plot_full, plot_zoom

# --- Paths -----------------------------------------------------------------
# Windows: use a raw string (r"...") so backslashes work, OR forward slashes.
#   CSV = r"C:\Users\you\Documents\H12\2026-06-11T10_18_53-06_00.csv"
#   CSV = "C:/Users/you/Documents/H12/2026-06-11T10_18_53-06_00.csv"
# OUT_DIR = None writes images next to where you run from; or set a folder.
CSV = r"C:\Users\dandresky\Documents\Spyder Projects\STE Console CSV Plotter\Data\2026_06_23T11_51_46_06_00.csv"
OUT_DIR = r"C:\Users\dandresky\Documents\Spyder Projects\STE Console CSV Plotter\Output"

# ===========================================================================
# Available parameter constants (match the CSV column headers).
# Pick from these when building AXIS1 / AXIS2 below.
# ===========================================================================

# --- Voltages (mV -> V) ----------------------------------------------------
ANODE_INPUT_V           = "anode_input_v"
ANODE_FILTERED_V        = "anode_filtered_v"
ANODE_VOUT              = "anode_vout"        # typically 300-500 V
KEEPER_FLYBACK          = "keeper_flyback"
MAGNET_VOUT             = "magnet_vout"
KEEPER_VOUT_SCOPE_MEAN  = "keeper_vout_scope_mean"
KEEPER_VOUT_SCOPE_MAX   = "keeper_vout_scope_max"
ANODE_VOUT_SCOPE_MEAN   = "anode_vout_scope_mean"
MAGNET_VOUT_SCOPE_MEAN  = "magnet_vout_scope_mean"

# --- Currents (mA -> A) ----------------------------------------------------
ANODE_X_SWITCH          = "anode_x_switch"    # ~5-15 A
ANODE_Y_SWITCH          = "anode_y_switch"    # ~5-15 A
ANODE_IOUT              = "anode_iout"
KEEPER_IOUT             = "keeper_iout"
MAGNET_IOUT             = "magnet_iout"
KEEPER_IOUT_SCOPE_MEAN  = "keeper_iout_scope_mean"
ANODE_IOUT_SCOPE_MEAN   = "anode_iout_scope_mean"
MAGNET_IOUT_SCOPE_MEAN  = "magnet_iout_scope_mean"

# --- Temperatures (Celsius) ------------------------------------------------
TEMP_THRUSTER    = "temp_thruster"
TEMP_KEEPER_MCU  = "temp_keeper_mcu"
TEMP_PDS         = "temp_pds"
TEMP_ANODE_MCU   = "temp_anode_mcu"
TEMP_MAGNET_MCU  = "temp_magnet_mcu"

# --- Pressures -------------------------------------------------------------
PRESSURE_TANK    = "pressure_tank"     # psi, integer
PRESSURE_ANODE   = "pressure_anode"    # milli-psi -> psi
PRESSURE_CATHODE = "pressure_cathode"  # milli-psi -> psi
PRESSURE_REG     = "pressure_reg"      # milli-psi -> psi

# ===========================================================================
# Choose what goes on each axis.
#   AXIS1 -> left axis  (cool color family)
#   AXIS2 -> right axis (warm color family)
# All signals within one axis must share a unit type.
# ===========================================================================
AXIS1 = [KEEPER_VOUT_SCOPE_MEAN, KEEPER_VOUT_SCOPE_MAX]    # left axis (voltage)
AXIS2 = [KEEPER_IOUT_SCOPE_MEAN]    # right axis (current)

# ===========================================================================
# Full-length plots: each entry is (left_signals, right_signals).
# ===========================================================================
FULL = [
    (AXIS1, AXIS2),
]

# ===========================================================================
# Zoom plots: each entry is (left_signals, right_signals, start_sec, end_sec).
# Leave the list empty ( ZOOMS = [] ) if you don't want any zoom plots.
# ===========================================================================
ZOOMS = [
    # (AXIS1, AXIS2, 30, 300),
]

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    for left, right in FULL:
        print(plot_full(CSV, left, right, OUT_DIR))
    for left, right, a, b in ZOOMS:
        print(plot_zoom(CSV, left, right, a, b, OUT_DIR))
