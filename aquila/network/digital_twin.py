"""
Hydraulic and Water Quality Digital Twin Engine for Aquila.
Simulates steady-state and extended-period hydraulic behavior using Hazen-Williams
head-loss formulations, nodal mass balances, and first-order chemical kinetics.
Provides high-fidelity baseline physical state against which cyber anomalies are verified.
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional
from aquila.network.topologies import WaterNetwork, Node, Pipe


class DigitalTwinEngine:
    """
    Simulates water distribution network hydraulics and water quality.
    Solves for nodal heads (pressures) and pipe flow rates using iterative
    hydraulic gradient relaxation, ensuring physical consistency with
    conservation of mass (Kirchhoff's Current Law) and energy (Kirchhoff's Voltage Law).
    """

    def __init__(self, network: WaterNetwork):
        self.network = network
        self.junction_ids = [nid for nid, n in network.nodes.items() if n.type == "junction"]
        self.fixed_node_ids = [nid for nid, n in network.nodes.items() if n.type in ("reservoir", "tank")]
        self.pipe_ids = list(network.pipes.keys())
        
        # Diurnal 24-hour demand pattern (hourly multipliers)
        self.diurnal_multipliers = [
            0.62, 0.55, 0.52, 0.58, 0.75, 1.15,
            1.48, 1.62, 1.35, 1.10, 1.05, 1.02,
            0.98, 0.95, 0.98, 1.08, 1.25, 1.55,
            1.68, 1.45, 1.20, 0.98, 0.82, 0.70
        ]
        
        # Baseline water quality constants
        self.chlorine_decay_rate = 0.05  # 1/hour bulk reaction rate
        self.source_chlorine = 1.40      # mg/L at reservoir
        self.source_turbidity = 0.35     # NTU
        self.source_ph = 7.45

    def get_demand_multiplier(self, hour: float) -> float:
        """Interpolates diurnal residential/commercial demand multiplier for a given fractional hour."""
        idx = int(hour) % 24
        next_idx = (idx + 1) % 24
        frac = hour - int(hour)
        return self.diurnal_multipliers[idx] * (1.0 - frac) + self.diurnal_multipliers[next_idx] * frac

    def _pipe_resistance(self, pipe: Pipe) -> float:
        """
        Computes Hazen-Williams hydraulic resistance coefficient k:
        head loss h_f = k * |Q|^1.852
        where L is in m, D is in m, C is Hazen-Williams roughness.
        Q is in m^3/s.
        h_f = 10.67 * L / (C^1.852 * D^4.87) * Q^1.852
        """
        d_m = pipe.diameter / 1000.0  # mm to m
        c = pipe.roughness
        l = pipe.length
        # 10.67 * L / (C^1.852 * D^4.87)
        k = 10.67 * l / ((c ** 1.852) * (d_m ** 4.8704))
        return k

    def solve_hydraulics(
        self,
        demand_mult: float = 1.0,
        leak_node: Optional[str] = None,
        leak_discharge_coeff: float = 0.0,
        base_head_boost: float = 0.0
    ) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        Solves hydraulic network state:
        Returns:
            pressures: dict of node_id -> pressure in meters (bar = m / 10.2)
            heads: dict of node_id -> piezometric head in meters
            flows: dict of pipe_id -> flow rate in Liters/sec (L/s) (positive from -> to)
        """
        # Node heads initialization
        heads: Dict[str, float] = {}
        for nid, node in self.network.nodes.items():
            if node.type == "reservoir":
                heads[nid] = self.network.reservoir_head + base_head_boost
            elif node.type == "tank":
                heads[nid] = self.network.nodes[nid].elevation + 15.0
            else:
                heads[nid] = self.network.reservoir_head - (node.elevation - 15.0) * 0.5

        # Effective nodal demands in m^3/s
        demands_m3s: Dict[str, float] = {}
        for nid, node in self.network.nodes.items():
            demands_m3s[nid] = (node.base_demand * demand_mult) / 1000.0

        # Iterative pressure-gradient relaxation (robust non-linear solver)
        max_iters = 120
        tolerance = 1e-5

        for iteration in range(max_iters):
            max_head_diff = 0.0
            new_heads = heads.copy()

            # For each junction, adjust head to balance in-and-out flow
            for jid in self.junction_ids:
                j_elev = self.network.nodes[jid].elevation
                leak_q = 0.0
                if jid == leak_node and leak_discharge_coeff > 0.0:
                    current_p = max(0.0, heads[jid] - j_elev)
                    leak_q = leak_discharge_coeff * math.sqrt(2.0 * 9.81 * current_p)  # m^3/s

                j_demand = demands_m3s[jid] + leak_q

                # Calculate sum of connected pipe conductances
                sum_conductance = 0.0
                sum_conductance_head = 0.0

                for pid, pipe in self.network.pipes.items():
                    k = self._pipe_resistance(pipe)
                    if pipe.from_node == jid:
                        other_id = pipe.to_node
                        dh = heads[jid] - heads[other_id]
                        # conductance G = |dh|^( (1-1.852)/1.852 ) / k^(1/1.852)
                        dh_eff = max(abs(dh), 1e-4)
                        # flow Q = sign(dh) * (dh_eff / k)^(1/1.852)
                        inv_exp = 1.0 / 1.852
                        q_mag = (dh_eff / k) ** inv_exp
                        g = q_mag / dh_eff
                        sum_conductance += g
                        sum_conductance_head += g * heads[other_id]

                    elif pipe.to_node == jid:
                        other_id = pipe.from_node
                        dh = heads[other_id] - heads[jid]
                        dh_eff = max(abs(dh), 1e-4)
                        inv_exp = 1.0 / 1.852
                        q_mag = (dh_eff / k) ** inv_exp
                        g = q_mag / dh_eff
                        sum_conductance += g
                        sum_conductance_head += g * heads[other_id]

                if sum_conductance > 1e-9:
                    # New head to satisfy Kirchhoff balance
                    target_head = (sum_conductance_head - j_demand) / sum_conductance
                    # Damped relaxation
                    updated = heads[jid] * 0.45 + target_head * 0.55
                    diff = abs(updated - heads[jid])
                    if diff > max_head_diff:
                        max_head_diff = diff
                    new_heads[jid] = updated

            heads = new_heads
            if max_head_diff < tolerance:
                break

        # Calculate pipe flows from final heads
        flows_ls: Dict[str, float] = {}
        for pid, pipe in self.network.pipes.items():
            k = self._pipe_resistance(pipe)
            h_from = heads[pipe.from_node]
            h_to = heads[pipe.to_node]
            dh = h_from - h_to
            dh_mag = abs(dh)
            if dh_mag < 1e-7:
                flows_ls[pid] = 0.0
            else:
                flow_m3s = math.copysign((dh_mag / k) ** (1.0 / 1.852), dh)
                flows_ls[pid] = flow_m3s * 1000.0  # m^3/s to L/s

        # Calculate gauge pressure (head minus elevation) in meters of water column
        pressures_m: Dict[str, float] = {}
        for nid, node in self.network.nodes.items():
            pressures_m[nid] = max(0.0, heads[nid] - node.elevation)

        return pressures_m, heads, flows_ls

    def simulate_water_quality(
        self,
        heads: Dict[str, float],
        flows: Dict[str, float],
        contaminant_node: Optional[str] = None,
        contaminant_magnitude: float = 0.0
    ) -> Dict[str, Dict[str, float]]:
        """
        Simulates water quality variables at each node:
        - Free Chlorine residual (mg/L): decay with distance/age from treatment plant.
        - Turbidity (NTU): low baseline, surges under back-siphonage or contamination.
        - pH: buffered 7.2 - 7.6 baseline, shifts under contaminant intrusion.
        """
        wq: Dict[str, Dict[str, float]] = {}

        # Distance approximation from reservoir R1
        for nid, node in self.network.nodes.items():
            dist_factor = math.sqrt((node.x - 50)**2 + (node.y - 300)**2) / 750.0
            chlorine = max(0.2, self.source_chlorine - dist_factor * 0.45)
            turbidity = self.source_turbidity + dist_factor * 0.12
            ph = self.source_ph - dist_factor * 0.08

            # If node is affected by contaminant injection
            if contaminant_node == nid and contaminant_magnitude > 0.0:
                chlorine = max(0.01, chlorine - 0.95 * contaminant_magnitude)
                turbidity = turbidity + 8.5 * contaminant_magnitude
                ph = ph - 1.8 * contaminant_magnitude

            # Downstream propagation check
            if contaminant_node is not None and contaminant_magnitude > 0.0:
                c_node = self.network.nodes[contaminant_node]
                # If downstream (higher x coordinate), receive decayed plume
                if node.x > c_node.x:
                    downstream_dist = math.sqrt((node.x - c_node.x)**2 + (node.y - c_node.y)**2)
                    decay_factor = math.exp(-downstream_dist / 350.0) * contaminant_magnitude
                    chlorine = max(0.05, chlorine - 0.70 * decay_factor)
                    turbidity = turbidity + 5.2 * decay_factor
                    ph = ph - 1.1 * decay_factor

            wq[nid] = {
                "chlorine": round(chlorine, 3),
                "turbidity": round(turbidity, 3),
                "ph": round(ph, 3),
            }

        return wq
