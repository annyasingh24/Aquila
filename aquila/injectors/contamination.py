"""
Water Quality Contamination Injector for Aquila.
Simulates intentional back-siphonage, sewage ingress, or chemical injection events.
Features realistic chlorine consumption (free chlorine depletion), turbidity turbidity rise,
and pH swings that transport downstream along pipe networks.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class ContaminationConfig:
    node_id: str
    contaminant_type: str  # 'organic_waste', 'industrial_acid', 'pathogen_backflow'
    severity: float  # 0.0 to 1.0
    start_hour: float = 10.0
    duration_hours: float = 4.0
    active: bool = False

    def get_intensity(self, current_hour: float) -> float:
        if not self.active or current_hour < self.start_hour:
            return 0.0
        elapsed = current_hour - self.start_hour
        if elapsed > self.duration_hours:
            # Trailing tail decay
            decay_hours = elapsed - self.duration_hours
            return max(0.0, self.severity * (0.5 ** (decay_hours / 1.5)))
        return self.severity
