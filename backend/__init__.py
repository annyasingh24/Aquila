"""
AQUILA: Physics-Aware AI Guardian for Municipal Water Networks
==============================================================
"""

from backend.config import (
    GRID, SPACING, SOURCE, HOSPITALS, H_SOURCE, MIN_PRESSURE, DT,
    LEGACY_DELAY_H, CREW_COST_INR, WATER_INR_PER_M3
)
from backend.digital_twin import HydraulicTwin, demand_mult
from backend.simulation import PhysicalWorld
from backend.legacy_scada import LegacySCADA
from backend.flight_recorder import AuditLog
from backend.notifier import Notifier
from backend.engine import Aquila, Simulation

__all__ = [
    "GRID",
    "SPACING",
    "SOURCE",
    "HOSPITALS",
    "H_SOURCE",
    "MIN_PRESSURE",
    "DT",
    "LEGACY_DELAY_H",
    "CREW_COST_INR",
    "WATER_INR_PER_M3",
    "HydraulicTwin",
    "demand_mult",
    "PhysicalWorld",
    "LegacySCADA",
    "AuditLog",
    "Notifier",
    "Aquila",
    "Simulation",
]
