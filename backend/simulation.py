"""
AQUILA Physical World & Cyberattack Packet Injector
===================================================
Models ground-truth physical state (reservoir head, orifice leaks, toxic plumes)
and synthesizes authentic sensor packets alongside adversary forged packets.
"""

import math
import numpy as np

from backend.config import (
    P_NOISE, CL_NOISE, TU_NOISE, METER_NOISE, FS, WAVE_T, WAVE_SPEED
)
from backend.digital_twin import HydraulicTwin, demand_mult


class PhysicalWorld:
    """Ground truth + IoT sensor layer + adversary attacker (Saboteur Mode)."""

    def __init__(self, seed=1):
        self.net = HydraulicTwin()
        self.rng = np.random.default_rng(seed)
        self.t = 360
        self.tick = 0
        self.leaks = {}
        self.contam = {}
        self.spoofs = {}
        self.valves = {}
        self.blocked_ips = set()
        self._new_cracks = []
        self.truth = None

    def expected_demand(self):
        """Calculates nominal city base demand modulated by diurnal curve."""
        return self.net.base_demand * demand_mult(self.t)

    # ---- Saboteur Mode Injections ------------------------------------------
    def burst_pipe(self, node, lps=25.0):
        """Simulates physical pipe burst at given node (liters per second)."""
        self.leaks[node] = lps / 1000.0

    def contaminate(self, node, strength=0.02):
        """Injects chemical / biological contaminant at given junction."""
        self.contam[node] = strength

    def hack_sensor(self, node, mode="fake_burst", hacker=True):
        """
        Spoofs sensor telemetry:
        modes: fake_burst | hide_leak | fake_chlorine | hide_contam | drift
        """
        self.spoofs[node] = dict(mode=mode, hacker=hacker, ip="185.220.101.47")

    def crack_pipe(self, node):
        """Injects acoustic high-frequency stress wave for micro-crack detection."""
        self._new_cracks.append(node)

    def repair_all(self):
        """Resets all faults, attacks, and valve quarantines."""
        self.leaks.clear()
        self.contam.clear()
        self.spoofs.clear()
        self.valves.clear()
        self.blocked_ips.clear()

    # ---- Simulation Tick ---------------------------------------------------
    def step(self):
        """Advances physical world by 1 minute, generating IoT telemetry packets."""
        net, rng = self.net, self.rng
        self.tick += 1
        self.t += 1
        exp = self.expected_demand()
        dem = np.clip(exp * (1 + 0.03 * rng.standard_normal(net.n)), 0, None)
        sol = net.solve(dem, self.valves, self.leaks)
        cl, tu, con = net.quality(sol, self.contam)
        base = net.solve(exp, self.valves)
        bcl, btu, _ = net.quality(base)
        h, z = sol["h"], net.z

        frames = []
        for i in range(net.n):
            f = dict(
                node=i,
                pressure=h[i] - z[i] + rng.normal(0, P_NOISE),
                chlorine=cl[i] + rng.normal(0, CL_NOISE),
                turbidity=tu[i] + rng.normal(0, TU_NOISE),
                src_ip=net.ip[i],
                ttl=64,
                hmac_ok=True,
                mac=f"02:aq:{i:02x}:00:00:01",
                seq=self.tick
            )
            sp = self.spoofs.get(i)
            if sp and not (sp["hacker"] and sp["ip"] in self.blocked_ips):
                m = sp["mode"]
                if m == "fake_burst":
                    f["pressure"] = 0.4
                elif m == "hide_leak":
                    f["pressure"] = base["h"][i] - z[i] + rng.normal(0, P_NOISE)
                elif m == "fake_chlorine":
                    f["chlorine"], f["turbidity"] = 0.05, 3.5
                elif m == "hide_contam":
                    f["chlorine"], f["turbidity"] = bcl[i], btu[i]
                elif m == "drift":
                    f["pressure"] += 2.5

                if sp["hacker"]:
                    # Synthesize rogue packet fingerprints
                    f.update(src_ip=sp["ip"], ttl=52, hmac_ok=False, mac="de:ad:be:ef:13:37")
            frames.append(f)

        wave = self._acoustic()
        self.truth = dict(sol=sol, cl=cl, tu=tu, con=con)
        return dict(
            frames=frames,
            meter=sol["inflow"] + rng.normal(0, METER_NOISE),
            wave=wave,
            truth=self.truth,
            tick=self.tick,
            t=self.t
        )

    def _acoustic(self):
        """Simulates hydrophone acoustic wave propagation along metallic pipes."""
        n, rng = self.net.n, self.rng
        S = int(FS * WAVE_T)
        tt = np.arange(S) / FS
        wave = rng.normal(0, 0.02, (n, S))
        for c in self._new_cracks:
            t0 = 0.3
            for i in range(n):
                d = self.net.dist[c, i]
                ta = t0 + d / WAVE_SPEED
                m = tt > ta
                amp = 3.0 / (1 + d / 250.0)
                wave[i, m] += (
                    amp * np.exp(-(tt[m] - ta) / 0.03) * np.sin(2 * math.pi * 80 * (tt[m] - ta))
                )
        self._new_cracks = []
        return wave
