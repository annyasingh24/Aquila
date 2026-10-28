"""
AQUILA Benchmark: Legacy SCADA System Model
===========================================
Simulates conventional municipal SCADA relying on naive static thresholds.
Highlights vulnerability to ghost dispatches and silent undetected leaks.
"""

from backend.config import CREW_COST_INR, DT
from backend.digital_twin import demand_mult


class LegacySCADA:
    """Blindly trusts every sensor; fixed alarm thresholds; dispatches digging crews."""

    P_DROP_ALARM = 1.5   # meters pressure drop threshold
    CL_ALARM = 0.20      # mg/L minimum safe chlorine threshold

    def __init__(self, net):
        self.net = net
        nominal = net.solve(net.base_demand * demand_mult(360))
        self.nominal_p = nominal["h"] - net.z
        self.alarms = []
        self.dispatches = []
        self.active = set()
        self.ghost_dispatches = 0
        self.wasted_inr = 0
        self.undetected_litres = 0.0

    def step(self, tk, world):
        """Processes one telemetry tick, accumulating wasted crew costs or missed leaks."""
        tr = tk["truth"]
        real_nodes = (
            set(world.leaks)
            | {j for k in world.leaks for j, _ in self.net.nbrs[k]}
            | {i for i in range(self.net.n) if tr["con"][i] > 0.03}
        )
        alarmed_now = set()
        for f in tk["frames"]:
            i = f["node"]
            bad = (
                (self.nominal_p[i] - f["pressure"] > self.P_DROP_ALARM)
                or (f["chlorine"] < self.CL_ALARM)
            )
            if bad:
                alarmed_now.add(i)
                if i not in self.active:
                    ghost = i not in real_nodes
                    self.alarms.append((tk["tick"], i, "ALARM"))
                    self.dispatches.append((tk["tick"], i, ghost))
                    self.wasted_inr += CREW_COST_INR
                    if ghost:
                        self.ghost_dispatches += 1

        self.active = alarmed_now
        for k, q in tr["sol"]["leakq"].items():
            if not any(d[1] in ({k} | {j for j, _ in self.net.nbrs[k]}) for d in self.dispatches):
                self.undetected_litres += q * DT * 1000
