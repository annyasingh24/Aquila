"""
AQUILA Configuration & Physical Constants
=========================================
Defines network grid topology, physical fluid parameters, sensor tolerances,
and economic impact metrics.
"""

import math
import numpy as np

# Network Geometry
GRID = 5                     # 5x5 junction grid (25 sensors)
SPACING = 100.0              # metres between junctions
SOURCE = 0                   # reservoir / water treatment plant node
HOSPITALS = {13: "City Hospital", 21: "Care Clinic"}

# Hydraulic & Pressure Floor Parameters
H_SOURCE = 70.0              # reservoir head (m)
MIN_PRESSURE = 15.0          # service pressure floor for critical infrastructure (m)
DT = 60.0                    # seconds per simulation tick
PIPE_AREA = math.pi * 0.15 ** 2

# Chemical Water Quality Parameters
CL_DOSE = 0.9                # standard disinfection dosing (mg/L)
CL_DECAY = 1 / (6 * 3600.0)  # natural wall/bulk reaction decay
CL_ALPHA = 2.5               # toxin stoichiometric neutralization consumption

# Sensor Gaussian Noise Thresholds
P_NOISE = 0.015              # pressure noise standard deviation
CL_NOISE = 0.01              # chlorine noise
TU_NOISE = 0.03              # turbidity noise
METER_NOISE = 0.0004         # ultrasonic inflow meter noise
VOTE_TOL = 0.25              # m: neighbour must disagree by this much to cast liar vote

# Economic ROI Metrics (City Disruption & Water Savings)
LEGACY_DELAY_H = 72          # hours a silent leak runs before anyone notices
CREW_COST_INR = 60_000       # emergency road-excavation crew dispatch cost
WATER_INR_PER_M3 = 30.0
ENERGY_KWH_PER_M3 = 0.6
INR_PER_KWH = 8.0

# Acoustic Micro-Crack Parameters
FS = 2000
WAVE_T = 1.5
WAVE_SPEED = 1100.0          # speed of sound in pressurized cast-iron water pipe (m/s)


def json_sanitize(o):
    """Serialize numpy data types into standard JSON primitives."""
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)
