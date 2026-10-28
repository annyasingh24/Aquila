"""
Sensor Model & Eco-Harvesting Energy Management for Aquila.
Models physical sensor instrumentation across the water network with:
- Measurement noise and resolution limits
- Micro-hydro energy harvesting from pipe flow kinetics
- Adaptive telemetry sleep/wake cycles to maximize sensor longevity and eliminate battery e-waste.
"""

from dataclasses import dataclass
import random
import math
from typing import Dict, Any, List


@dataclass
class SensorDevice:
    id: str
    location_id: str  # node or pipe ID
    sensor_type: str  # 'pressure', 'flow', 'water_quality'
    unit: str
    baseline_noise_std: float
    battery_level_pct: float = 95.0
    has_energy_harvester: bool = True  # In-pipe micro-turbine or solar harvester
    harvest_power_mw: float = 8.5      # Milliwatts continuously harvested from pipe flow
    quiescent_power_mw: float = 0.4    # Sleep state power draw
    tx_power_mw: float = 45.0          # Active transmission power draw
    sample_interval_sec: int = 60      # Adaptive: 600s in normal state, 15s in alert state
    is_compromised: bool = False
    spoofed_value: float = 0.0

    def calculate_power_sustainability(self, alert_active: bool = False) -> Dict[str, Any]:
        """
        Calculates net energy balance and projected battery lifespan.
        Green edge architecture: If harvested power > average consumption,
        the sensor achieves energy autarky (infinite battery lifespan, zero e-waste).
        """
        interval = 15 if alert_active else self.sample_interval_sec
        # Duty cycle fraction
        duty_cycle = 2.0 / interval  # 2 seconds active per interval
        avg_consumption_mw = (duty_cycle * self.tx_power_mw) + ((1.0 - duty_cycle) * self.quiescent_power_mw)
        net_power_mw = self.harvest_power_mw - avg_consumption_mw if self.has_energy_harvester else -avg_consumption_mw

        if net_power_mw >= 0:
            lifespan_years = 25.0  # Self-powered energy autarky (limited only by capacitor/battery cycle degradation)
            status = "Energy Autarkic (Micro-Hydro Harvested)"
        else:
            # Remaining hours from 3500 mAh 3.6V cell = 12,600 mWh
            remaining_mwh = (self.battery_level_pct / 100.0) * 12600.0
            lifespan_hours = remaining_mwh / abs(net_power_mw)
            lifespan_years = round(lifespan_hours / (24 * 365), 1)
            status = "Battery Discharging"

        return {
            "avg_power_consumption_mw": round(avg_consumption_mw, 2),
            "harvested_power_mw": round(self.harvest_power_mw if self.has_energy_harvester else 0.0, 2),
            "net_power_balance_mw": round(net_power_mw, 2),
            "projected_lifespan_years": lifespan_years,
            "sustainability_status": status,
        }


class SensorNetworkManager:
    """Manages the network-wide array of telemetry instruments."""

    def __init__(self):
        self.sensors: Dict[str, SensorDevice] = {}
        self._initialize_default_sensors()

    def _initialize_default_sensors(self):
        # Pressure sensors at key junctions
        pressure_nodes = ["J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9", "J10"]
        for nid in pressure_nodes:
            sid = f"PT_{nid}"
            self.sensors[sid] = SensorDevice(
                id=sid,
                location_id=nid,
                sensor_type="pressure",
                unit="bar",
                baseline_noise_std=0.03,
                has_energy_harvester=True,
            )

        # Flow meters at critical transmission and trunk pipes
        flow_pipes = ["P1", "P2", "P3", "P4", "P7", "P8", "P11", "P12", "P15"]
        for pid in flow_pipes:
            sid = f"FM_{pid}"
            self.sensors[sid] = SensorDevice(
                id=sid,
                location_id=pid,
                sensor_type="flow",
                unit="L/s",
                baseline_noise_std=0.25,
                has_energy_harvester=True,
                harvest_power_mw=12.0,  # Higher kinetic energy in main pipes
            )

        # Water quality multi-parameter stations
        wq_nodes = ["J1", "J5", "J7", "J10"]
        for nid in wq_nodes:
            sid = f"WQ_{nid}"
            self.sensors[sid] = SensorDevice(
                id=sid,
                location_id=nid,
                sensor_type="water_quality",
                unit="multi",
                baseline_noise_std=0.02,
                has_energy_harvester=True,
            )

    def read_telemetry(
        self,
        true_pressures: Dict[str, float],
        true_flows: Dict[str, float],
        true_wq: Dict[str, Dict[str, float]],
        seed: int = None
    ) -> Dict[str, Any]:
        """
        Generates noisy, digitized telemetry readings from ground truth physical twin.
        Converts meters of head to bar (1 bar = 10.197 meters).
        """
        rng = random.Random(seed) if seed is not None else random
        readings = {}

        for sid, sensor in self.sensors.items():
            if sensor.sensor_type == "pressure":
                true_val_m = true_pressures.get(sensor.location_id, 25.0)
                true_bar = true_val_m / 10.197
                noise = rng.gauss(0.0, sensor.baseline_noise_std)
                measured = max(0.0, true_bar + noise)
                readings[sid] = round(measured, 3)

            elif sensor.sensor_type == "flow":
                true_val_ls = true_flows.get(sensor.location_id, 0.0)
                noise = rng.gauss(0.0, sensor.baseline_noise_std)
                measured = true_val_ls + noise
                readings[sid] = round(measured, 2)

            elif sensor.sensor_type == "water_quality":
                wq_data = true_wq.get(sensor.location_id, {"chlorine": 1.1, "turbidity": 0.4, "ph": 7.4})
                readings[sid] = {
                    "chlorine": round(max(0.0, wq_data["chlorine"] + rng.gauss(0, 0.02)), 3),
                    "turbidity": round(max(0.05, wq_data["turbidity"] + rng.gauss(0, 0.03)), 3),
                    "ph": round(max(5.0, min(9.0, wq_data["ph"] + rng.gauss(0, 0.02))), 3),
                }

        return readings
