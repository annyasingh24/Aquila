"""
Cyberattack Library for Smart Water Network Telemetry.
Simulates realistic adversary techniques targeting SCADA, RTU, and IoT edge sensors:
1. Replay Attack: Telemetry hijacked and replayed from previous baseline window.
2. Stealth Drift Attack: Slow ramping sensor bias to evade static thresholds.
3. Spike / False-Leak Injection: Single-sensor false depression designed to cause phantom truck rolls.
4. Noise Flooding: Channel jamming to mask real anomalies.
5. Sensor Dropout / Freezing: Data stream stuck or corrupted.
"""

from dataclasses import dataclass, field
import random
import math
from typing import Dict, Any, List, Optional


@dataclass
class CyberAttackConfig:
    attack_type: str  # 'spike_fake_leak', 'drift', 'replay', 'noise_flooding', 'dropout'
    target_sensor_id: str
    start_hour: float = 7.0
    duration_hours: float = 5.0
    magnitude: float = 1.0  # Normalized multiplier or offset
    active: bool = False
    replay_buffer: List[Any] = field(default_factory=list)

    def apply_attack(
        self,
        sensor_id: str,
        clean_value: Any,
        current_hour: float,
        step_index: int = 0
    ) -> Any:
        """
        Applies cyber tampering to the telemetry reading if sensor matches target.
        """
        if not self.active or sensor_id != self.target_sensor_id:
            return clean_value

        if current_hour < self.start_hour or current_hour > (self.start_hour + self.duration_hours):
            return clean_value

        elapsed = current_hour - self.start_hour

        # Handle numeric sensors (pressure or flow)
        if isinstance(clean_value, (int, float)):
            if self.attack_type == "spike_fake_leak":
                # Fakes a massive pressure drop (e.g. -1.2 bar) or flow surge
                drop = 1.25 * self.magnitude
                return max(0.05, round(clean_value - drop, 3))

            elif self.attack_type == "drift":
                # Stealth gradual drift: 0.15 bar per hour
                drift_offset = 0.18 * elapsed * self.magnitude
                return round(clean_value - drift_offset, 3)

            elif self.attack_type == "noise_flooding":
                noise = random.gauss(0, 0.45 * self.magnitude)
                return max(0.0, round(clean_value + noise, 3))

            elif self.attack_type == "dropout":
                # Sticking / freeze at stale reading or zero
                if self.magnitude > 0.5:
                    return 0.0  # Complete signal loss
                return 1.45  # Frozen stuck value

            elif self.attack_type == "replay":
                # Replay historical steady reading from early morning
                return round(clean_value * 0.72 + 0.35, 3)

        # Handle water quality dicts
        elif isinstance(clean_value, dict):
            spoofed = clean_value.copy()
            if self.attack_type == "spike_fake_leak":
                spoofed["chlorine"] = 0.02  # Fake sudden chlorine loss
            elif self.attack_type == "noise_flooding":
                spoofed["turbidity"] = round(spoofed["turbidity"] + abs(random.gauss(0, 3.5)), 2)
            return spoofed

        return clean_value
