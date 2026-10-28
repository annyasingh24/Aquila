"""
Physical Leak Injector for Aquila.
Simulates real structural pipe failure, orifice punctures, and joint ruptures.
Generates genuine physical changes: nodal pressure depression, gradient shifts,
and network mass inflow surges.
"""

from dataclasses import dataclass
import math
from typing import Optional, Dict, Any


@dataclass
class PhysicalLeakConfig:
    pipe_id: str
    nearest_node: str
    leak_size: str  # 'minor' (0.5 - 2 L/s), 'medium' (5 - 12 L/s), 'major_burst' (20 - 45 L/s)
    orifice_diameter_mm: float
    discharge_coefficient_cd: float = 0.62
    start_hour: float = 8.0
    ramp_duration_hours: float = 0.25  # Burst vs gradual rupture
    active: bool = False

    @classmethod
    def create_preset(cls, pipe_id: str, nearest_node: str, severity: str = "medium", start_hour: float = 6.0):
        if severity == "minor":
            diam = 12.0
        elif severity == "major_burst":
            diam = 45.0
        else:
            diam = 24.0

        return cls(
            pipe_id=pipe_id,
            nearest_node=nearest_node,
            leak_size=severity,
            orifice_diameter_mm=diam,
            discharge_coefficient_cd=0.62,
            start_hour=start_hour,
            ramp_duration_hours=0.2 if severity == "major_burst" else 0.8,
            active=True
        )

    def get_effective_emitter_coeff(self, current_hour: float) -> float:
        """
        Calculates effective emitter area discharge factor:
        emitter_coeff = C_d * A_orifice (in m^2)
        Q = emitter_coeff * sqrt(2 * g * P_head)
        """
        if not self.active or current_hour < self.start_hour:
            return 0.0

        elapsed = current_hour - self.start_hour
        progress = min(1.0, elapsed / max(0.01, self.ramp_duration_hours))

        # Area in m^2
        radius_m = (self.orifice_diameter_mm / 2000.0)
        area_m2 = math.pi * (radius_m ** 2)
        effective_coeff = self.discharge_coefficient_cd * area_m2 * progress
        return effective_coeff

    def estimate_loss_rate_ls(self, pressure_head_m: float, current_hour: float) -> float:
        """Estimates actual instantaneous water loss in Liters per second."""
        coeff = self.get_effective_emitter_coeff(current_hour)
        if coeff <= 0.0 or pressure_head_m <= 0.0:
            return 0.0
        # Q in m^3/s = coeff * sqrt(2 * 9.81 * H)
        q_m3s = coeff * math.sqrt(2.0 * 9.81 * pressure_head_m)
        return q_m3s * 1000.0  # L/s
