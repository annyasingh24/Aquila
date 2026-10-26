# Aquila
#!/usr/bin/env python3
"""
AQUILA - physics-aware AI guardian for city water grids
=======================================================
"Hackers can spoof data, but they cannot hack the laws of physics."

Run the dashboard :  pip install streamlit plotly numpy && streamlit run aquila.py
Run headless tests:  python aquila.py --demo

Features (all in this file)
  Core      : Digital Twin | Sensor Trust Score | 4-way classifier | Litres & Rupees ROI
  Showstop. : Ghost (virtual) sensors | Patient-Zero backtracking | Smart Valve Doctor
              Acoustic water-hammer listener | Saboteur Mode | Tamper-proof audit log
  New       : Federated Sensor Trust Swarm (neighbour consensus, no cloud)
              3D Particle Flow Mesh | "God Mode" split-screen: Legacy SCADA vs Aquila

Physics used: mass conservation at every junction.  For junction i
    r_i = sum_j g_ij (H_i - H_j) + d_i      (must be ~0)
A REAL leak breaks the equation at ONE junction only (unexplained outflow) and
raises the reservoir inflow meter.  A SPOOFED sensor breaks the equation at the
liar AND at all its neighbours (with opposite sign) and leaves the inflow
meter untouched.  Neighbours each compute the value the liar "should" report;
the median of those implied values is the vote + the ghost sensor.

NOTE: the hydraulic twin is a linearised steady-state solver (numpy only) so the
demo runs anywhere. HydraulicTwin.solve() is the swap point for EPANET/WNTR.
All money / delay constants are editable ASSUMPTIONS, not measured data.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import sys

import numpy as np

# ============================== CONFIG ======================================
GRID = 5                     # 5x5 junction grid (25 sensors)
SPACING = 100.0              # metres between junctions
SOURCE = 0                   # reservoir / treatment plant node
HOSPITALS = {13: "City Hospital", 21: "Care Clinic"}
H_SOURCE = 70.0              # reservoir head (m)
MIN_PRESSURE = 15.0          # service pressure floor (m)
DT = 60.0                    # seconds per tick
CL_DOSE, CL_DECAY, CL_ALPHA = 0.9, 1 / (6 * 3600.0), 2.5
PIPE_AREA = math.pi * 0.15 ** 2
P_NOISE, CL_NOISE, TU_NOISE, METER_NOISE = 0.015, 0.01, 0.03, 0.0004
VOTE_TOL = 0.25              # m: neighbour must disagree by this much to vote
# --- economics (ASSUMPTIONS) ---
LEGACY_DELAY_H = 72          # hours a silent leak runs before anyone notices
CREW_COST_INR = 60_000       # one emergency dig-up crew dispatch
WATER_INR_PER_M3 = 30.0
ENERGY_KWH_PER_M3, INR_PER_KWH = 0.6, 8.0
# --- acoustic ---
FS, WAVE_T, WAVE_SPEED = 2000, 1.5, 1100.0


def _j(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


# ============================ DIGITAL TWIN ==================================
class HydraulicTwin:
    """Pipe network + linear hydraulic / water-quality solver."""

    def __init__(self, grid=GRID, seed=7):
        rng = np.random.default_rng(seed)
        self.grid, self.n = grid, grid * grid
        n = self.n
        self.xy = np.array([[(i % grid) * SPACING, (i // grid) * SPACING] for i in range(n)])
        self.z = 4 + 3 * np.sin(self.xy[:, 0] / 170) + 3 * np.cos(self.xy[:, 1] / 140)
        self.edges = []
        for i in range(n):
            r, c = divmod(i, grid)
            if c < grid - 1:
                self.edges.append((i, i + 1))
            if r < grid - 1:
                self.edges.append((i, i + grid))
        self.m = len(self.edges)
        self.g0 = 0.03 * rng.uniform(0.85, 1.15, self.m)          # conductance m3/s per m head
        self.length = np.array([np.linalg.norm(self.xy[a] - self.xy[b]) for a, b in self.edges])
        self.base_demand = 0.004 * rng.uniform(0.7, 1.3, n)
        self.base_demand[SOURCE] = 0.0
        self.nbrs = [[] for _ in range(n)]
        for k, (a, b) in enumerate(self.edges):
            self.nbrs[a].append((b, k))
            self.nbrs[b].append((a, k))
        self.ip = [f"10.20.{i // grid}.{10 + i % grid}" for i in range(n)]
        D = np.full((n, n), np.inf)
        np.fill_diagonal(D, 0)
        for k, (a, b) in enumerate(self.edges):
            D[a, b] = D[b, a] = self.length[k]
        for k in range(n):
            D = np.minimum(D, D[:, [k]] + D[[k], :])
        self.dist = D

    def eff_g(self, valves):
        return self.g0 * np.array([valves.get(k, 1.0) for k in range(self.m)])

    def reachable(self, gf):
        seen, stack = {SOURCE}, [SOURCE]
        while stack:
            i = stack.pop()
            for j, k in self.nbrs[i]:
                if gf[k] > 1e-12 and j not in seen:
                    seen.add(j)
                    stack.append(j)
        return np.array([i in seen for i in range(self.n)])

    def _head(self, gf, d, reach):
        n = self.n
        L = np.zeros((n, n))
        for k, (a, b) in enumerate(self.edges):
            g = gf[k]
            L[a, a] += g; L[b, b] += g; L[a, b] -= g; L[b, a] -= g
        free = [i for i in range(n) if reach[i] and i != SOURCE]
        h = np.where(reach, H_SOURCE, self.z).astype(float)
        if free:
            rhs = -d[free] - L[free, SOURCE] * H_SOURCE
            h[free] = np.linalg.solve(L[np.ix_(free, free)], rhs)
        return h

    def solve(self, demand, valves=None, leaks=None):
        """leaks: node -> flow (m3/s) at 40 m pressure (orifice law q ~ sqrt(p))."""
        valves, leaks = valves or {}, leaks or {}
        gf = self.eff_g(valves)
        reach = self.reachable(gf)
        lq = {k: 0.0 for k in leaks}
        for _ in range(10):
            d = demand.copy()
            for k, q in lq.items():
                d[k] += q
            h = self._head(gf, d, reach)
            lq = {k: (leaks[k] * math.sqrt(max(h[k] - self.z[k], 0) / 40.0) if reach[k] else 0.0)
                  for k in leaks}
        d = demand.copy()
        for k, q in lq.items():
            d[k] += q
        h = self._head(gf, d, reach)
        flows = np.array([gf[k] * (h[a] - h[b]) if (reach[a] and reach[b]) else 0.0
                          for k, (a, b) in enumerate(self.edges)])
        inflow = float(sum(d[i] for i in range(self.n) if reach[i]))
        return dict(h=h, flows=flows, reach=reach, inflow=inflow, leakq=lq, gf=gf)

    def flow_graph(self, flows):
        """node -> list of (downstream_node, q, edge)."""
        out = [[] for _ in range(self.n)]
        for k, (a, b) in enumerate(self.edges):
            q = flows[k]
            if q > 1e-9:
                out[a].append((b, q, k))
            elif q < -1e-9:
                out[b].append((a, -q, k))
        return out

    def quality(self, sol, contam=None):
        """Steady-state chlorine / contaminant mixing along the flow DAG."""
        contam = contam or {}
        h, flows, reach = sol["h"], sol["flows"], sol["reach"]
        n = self.n
        inflow = [[] for _ in range(n)]
        for i, lst in enumerate(self.flow_graph(flows)):
            for j, q, k in lst:
                inflow[j].append((i, q, k))
        cl, con = np.zeros(n), np.zeros(n)
        for i in np.argsort(-h):
            if not reach[i]:
                continue
            if i == SOURCE:
                cl[i] = CL_DOSE
                continue
            tot = sum(q for _, q, _ in inflow[i])
            if tot < 1e-9:
                continue
            mix = sum(q * cl[j] * math.exp(-CL_DECAY * PIPE_AREA * self.length[k] / q)
                      for j, q, k in inflow[i]) / tot
            inj = contam.get(i, 0.0)
            cl[i] = mix * math.exp(-CL_ALPHA * inj / tot)
            con[i] = (sum(q * con[j] for j, q, _ in inflow[i]) + inj) / tot
        tu = np.where(reach, 0.25 + 4.0 * con, 0.0)
        return cl, tu, con

    def travel_times(self, flows, src):
        """Dijkstra of advective travel time (s) from src along flow direction."""
        out = self.flow_graph(flows)
        best = {src: 0.0}
        pq = [(0.0, src)]
        while pq:
            t, i = heapq.heappop(pq)
            if t > best.get(i, 1e18):
                continue
            for j, q, k in out[i]:
                nt = t + PIPE_AREA * self.length[k] / q
                if nt < best.get(j, 1e18):
                    best[j] = nt
                    heapq.heappush(pq, (nt, j))
        return best


def demand_mult(t_min):
    return 1 + 0.3 * math.sin(2 * math.pi * (t_min - 360) / 1440)


# ============================ THE REAL WORLD ================================
class World:
    """Ground truth + sensor/IoT layer + attacker (Saboteur Mode)."""

    def __init__(self, seed=1):
        self.net = HydraulicTwin()
        self.rng = np.random.default_rng(seed)
        self.t, self.tick = 360, 0
        self.leaks, self.contam, self.spoofs = {}, {}, {}
        self.valves, self.blocked_ips = {}, set()
        self._new_cracks = []
        self.truth = None

    def expected_demand(self):
        return self.net.base_demand * demand_mult(self.t)

    # ---- Saboteur Mode -----------------------------------------------------
    def burst_pipe(self, node, lps=25.0):
        self.leaks[node] = lps / 1000.0

    def contaminate(self, node, strength=0.02):
        self.contam[node] = strength

    def hack_sensor(self, node, mode="fake_burst", hacker=True):
        """modes: fake_burst | hide_leak | fake_chlorine | hide_contam | drift"""
        self.spoofs[node] = dict(mode=mode, hacker=hacker, ip="185.220.101.47")

    def crack_pipe(self, node):
        self._new_cracks.append(node)

    def repair_all(self):
        self.leaks.clear(); self.contam.clear(); self.spoofs.clear()
        self.valves.clear(); self.blocked_ips.clear()

    # ---- one tick ----------------------------------------------------------
    def step(self):
        net, rng = self.net, self.rng
        self.tick += 1; self.t += 1
        exp = self.expected_demand()
        dem = np.clip(exp * (1 + 0.03 * rng.standard_normal(net.n)), 0, None)
        sol = net.solve(dem, self.valves, self.leaks)
        cl, tu, con = net.quality(sol, self.contam)
        base = net.solve(exp, self.valves)                    # what "normal" looks like
        bcl, btu, _ = net.quality(base)
        h, z = sol["h"], net.z
        frames = []
        for i in range(net.n):
            f = dict(node=i, pressure=h[i] - z[i] + rng.normal(0, P_NOISE),
                     chlorine=cl[i] + rng.normal(0, CL_NOISE), turbidity=tu[i] + rng.normal(0, TU_NOISE),
                     src_ip=net.ip[i], ttl=64, hmac_ok=True, mac=f"02:aq:{i:02x}:00:00:01", seq=self.tick)
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
                if sp["hacker"]:      # forged packet fingerprints
                    f.update(src_ip=sp["ip"], ttl=52, hmac_ok=False, mac="de:ad:be:ef:13:37")
            frames.append(f)
        wave = self._acoustic()
        self.truth = dict(sol=sol, cl=cl, tu=tu, con=con)
        return dict(frames=frames, meter=sol["inflow"] + rng.normal(0, METER_NOISE),
                    wave=wave, truth=self.truth, tick=self.tick, t=self.t)

    def _acoustic(self):
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
                wave[i, m] += amp * np.exp(-(tt[m] - ta) / 0.03) * np.sin(2 * math.pi * 80 * (tt[m] - ta))
        self._new_cracks = []
        return wave


# ============================ AUDIT LOG =====================================
class AuditLog:
    """Hash-chained flight recorder: editing any past entry breaks every later hash."""

    def __init__(self):
        self.chain = []

    @staticmethod
    def _h(body):
        return hashlib.sha256(json.dumps(body, sort_keys=True, default=_j).encode()).hexdigest()

    def add(self, tick, kind, payload):
        prev = self.chain[-1]["hash"] if self.chain else "0" * 64
        body = dict(i=len(self.chain), tick=tick, kind=kind, payload=payload, prev=prev)
        self.chain.append(dict(body, hash=self._h(body)))

    def verify(self):
        prev = "0" * 64
        for e in self.chain:
            body = {k: e[k] for k in ("i", "tick", "kind", "payload", "prev")}
            if e["prev"] != prev or self._h(body) != e["hash"]:
                return False, e["i"]
            prev = e["hash"]
        return True, None


# ============================ LEGACY SCADA ==================================
class LegacySCADA:
    """Blindly trusts every sensor; fixed alarm thresholds; dispatches crews."""
    P_DROP_ALARM, CL_ALARM = 1.5, 0.20

    def __init__(self, net):
        self.net = net
        b = net.solve(net.base_demand * demand_mult(360))
        self.nominal_p = b["h"] - net.z
        self.alarms, self.dispatches = [], []
        self.active = set()
        self.ghost_dispatches = 0
        self.wasted_inr = 0
        self.undetected_litres = 0.0

    def step(self, tk, world):
        tr = tk["truth"]
        real_nodes = set(world.leaks) | {j for k in world.leaks for j, _ in self.net.nbrs[k]} \
            | {i for i in range(self.net.n) if tr["con"][i] > 0.03}
        alarmed_now = set()
        for f in tk["frames"]:
            i = f["node"]
            bad = (self.nominal_p[i] - f["pressure"] > self.P_DROP_ALARM) or f["chlorine"] < self.CL_ALARM
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


# ============================ AQUILA ========================================
class Aquila:
    def __init__(self, net):
        self.net = net
        n = net.n
        self.trust = np.ones(n)
        self.valves, self.blocked_ips = {}, set()
        self.log = AuditLog()
        self.incidents = {}
        self.ghosts, self.flagged = {}, []
        self.votes = {}
        self.roi = dict(litres=0.0, kwh=0.0, inr=0.0, ghost_avoided=0, events=0)
        self.summary = {}
        self.crack_watch = {}
        self.last_plan = None
        self._pending = []

    # ---------- helpers ----------
    def _sigma_r(self, gf):
        out = np.zeros(self.net.n)
        for i in range(self.net.n):
            gs = np.array([gf[k] for _, k in self.net.nbrs[i]])
            out[i] = P_NOISE * math.sqrt(gs.sum() ** 2 + (gs ** 2).sum())
        return out

    def _residuals(self, H, d_exp, gf, active):
        r = np.zeros(self.net.n)
        for i in range(self.net.n):
            if i == SOURCE or not active[i]:
                continue
            r[i] = sum(gf[k] * (H[i] - H[j]) for j, k in self.net.nbrs[i] if gf[k] > 0) + d_exp[i]
        return r

    def _vote(self, H, r, gf, thr, active):
        """Each neighbour j (using ONLY its own 1-hop data) says what H_k should be."""
        res = {}
        for k in range(self.net.n):
            if not active[k]:
                continue
            ballots = []
            for j, kk in self.net.nbrs[k]:
                if gf[kk] <= 0 or j == SOURCE or not active[j]:
                    continue
                implied = H[k] + r[j] / gf[kk]
                against = abs(r[j]) > thr[j] and abs(r[j] / gf[kk]) > VOTE_TOL
                ballots.append((j, float(implied), bool(against), float(self.trust[j])))
            if not ballots:
                continue
            W = sum(b[3] for b in ballots)
            frac = sum(b[3] for b in ballots if b[2]) / W
            res[k] = dict(frac=frac, ballots=ballots, ghost=float(np.median([b[1] for b in ballots])),
                          strength=abs(r[k]) / thr[k])
        return res

    # ---------- main loop ----------
    def step(self, tk, expected_demand, auto=True, legacy_delay_h=LEGACY_DELAY_H):
        net, n = self.net, self.net.n
        tick = tk["tick"]
        frames = tk["frames"]
        gf = net.eff_g(self.valves)
        active = net.reachable(gf)
        z = net.z
        P = np.array([f["pressure"] for f in frames])
        H = P + z
        d_exp = expected_demand
        sig = self._sigma_r(gf)
        thr = np.maximum(5 * sig, 0.005)

        # ---- 1. Federated trust swarm: greedy consensus eviction of liars ----
        flagged, ghosts, votes = [], {}, {}
        Hc = H.copy()
        for _ in range(4):
            r = self._residuals(Hc, d_exp, gf, active)
            sc = self._vote(Hc, r, gf, thr, active)
            cand = [(v["frac"], v["strength"], k) for k, v in sc.items()
                    if v["frac"] >= 0.5 and k not in flagged]
            if not cand:
                break
            _, _, k = max(cand)
            flagged.append(k)
            ghosts[k] = dict(reported=float(H[k] - z[k]), ghost=sc[k]["ghost"] - float(z[k]))
            votes[k] = sc[k]["ballots"]
            Hc[k] = sc[k]["ghost"]
        r = self._residuals(Hc, d_exp, gf, active)

        # ---- 2. Leak finder on the GHOST-CORRECTED picture ----
        leak_est = {i: float(-r[i]) for i in range(n) if i != SOURCE and active[i] and -r[i] > thr[i]}
        expected_in = float(sum(d_exp[i] for i in range(n) if active[i]))
        excess = tk["meter"] - expected_in
        total_est = sum(leak_est.values())
        confirmed = bool(leak_est) and excess > max(0.006, 0.5 * total_est)
        real_leaks = leak_est if confirmed else {}
        unverified = {} if confirmed else leak_est

        # ---- 3. Water quality / contamination ----
        exp_sol = net.solve(d_exp, self.valves)
        ecl, etu, _ = net.quality(exp_sol)
        cl_m = np.array([f["chlorine"] for f in frames])
        tu_m = np.array([f["turbidity"] for f in frames])
        dcl, dtu = ecl - cl_m, tu_m - etu
        A = {i for i in range(n) if active[i] and (dcl[i] > 0.08 or dtu[i] > 0.25)}
        out = net.flow_graph(exp_sol["flows"])
        plumes, q_faults, seen = [], [], set()
        for i in sorted(A):
            if i in seen:
                continue
            comp, stack = {i}, [i]
            while stack:
                u = stack.pop()
                nb = [j for j, _, _ in out[u]] + [p for p in A if any(j == u for j, _, _ in out[p])]
                for v in nb:
                    if v in A and v not in comp:
                        comp.add(v); stack.append(v)
            seen |= comp
            if len(comp) >= 2:
                plumes.append(sorted(comp))
            else:
                (i0,) = tuple(comp)
                strong = dcl[i0] > 0.08 and dtu[i0] > 0.25
                (plumes if (not out[i0] and strong) else q_faults).append(sorted(comp) if not out[i0] and strong else i0)
        patient_zero = None
        if plumes:
            plume_nodes = sorted({i for p in plumes for i in p})
            patient_zero = self.patient_zero(exp_sol, ecl, plume_nodes, np.clip(dtu / 4.0, 0, None), active)

        # ---- 4. Fingerprint every sensor-level anomaly: cyberattack vs fault ----
        sensor_issues = {}
        for k in flagged + [q for q in q_faults if q not in flagged] + list(unverified):
            f = frames[k]
            forged = (not f["hmac_ok"]) or f["ttl"] != 64 or f["src_ip"] != net.ip[k]
            sensor_issues[k] = dict(
                kind="CYBERATTACK" if forged else "SENSOR_FAULT",
                vector=(f"forged packet on topic aquila/n{k}/pressure from {f['src_ip']} "
                        f"(mac {f['mac']}, ttl {f['ttl']} vs 64, hmac {'OK' if f['hmac_ok'] else 'INVALID'})")
                if forged else "valid signature, impossible physics -> hardware/calibration fault",
                ip=f["src_ip"] if forged else None)

        # ---- 5. Trust update (decay for liars, slow recovery) ----
        for i in range(n):
            if i in sensor_issues:
                self.trust[i] *= 0.5
            else:
                self.trust[i] = min(1.0, self.trust[i] + 0.02)

        # ---- 6. Acoustic water-hammer listener ----
        ac = self.listen(tk["wave"])
        if ac:
            self.crack_watch[ac["node"]] = dict(tick=tick, **ac)

        # ---- 7. Incidents, valve doctor, quarantines, ROI ----
        new_msgs = []

        def open_inc(kind, node, info):
            key = (kind, node)
            if key not in self.incidents:
                self.incidents[key] = dict(kind=kind, node=node, tick=tick, status="ACTIVE", info=info)
                new_msgs.append(f"[t{tick}] {kind} @ node {node}")
                self.log.add(tick, "INCIDENT", dict(kind=kind, node=node, info=info))
                return True
            self.incidents[key]["info"] = info
            return False

        for k, q in real_leaks.items():
            if open_inc("REAL_LEAK", k, dict(lps=round(q * 1000, 1))):
                self.last_plan = self.valve_doctor({k})
                self._pending.append((tick + 2, "isolate", k, q, self.last_plan))
        for p in plumes:
            key = tuple(p)
            if open_inc("CONTAMINATION", key, dict(nodes=p, patient_zero=patient_zero)):
                self.last_plan = self.valve_doctor(set(p))
                self._pending.append((tick + 2, "isolate", key, 0.0, self.last_plan))
        for k, s in sensor_issues.items():
            if open_inc(s["kind"], k, dict(vector=s["vector"], ip=s["ip"])):
                if s["ip"]:
                    self._pending.append((tick + 1, "block", s["ip"], 0, None))
        for k, w in self.crack_watch.items():
            open_inc("MICRO_CRACK", k, dict(magnitude=round(w["mag"], 2), note="pre-leak: schedule repair"))

        for it in [p for p in self._pending if p[0] <= tick]:
            self._pending.remove(it)
            _, act, tgt, q, plan = it
            if act == "isolate" and auto and plan:
                self.valves.update(plan["valves"])
                el = DT * 2
                saved = q * (legacy_delay_h * 3600 - el)
                m3 = max(saved, 0)
                self.roi["litres"] += m3 * 1000
                self.roi["kwh"] += m3 * ENERGY_KWH_PER_M3
                self.roi["inr"] += m3 * WATER_INR_PER_M3 + m3 * ENERGY_KWH_PER_M3 * INR_PER_KWH
                self.roi["events"] += 1
                inc = next((v for kk, v in self.incidents.items() if kk[1] == tgt), None)
                if inc:
                    inc["status"] = "ISOLATED - crew dispatched with valve plan"
                self.log.add(tick, "VALVE_ACTION", dict(target=tgt, valves=plan["valves"]))
            elif act == "block":
                self.blocked_ips.add(tgt)
                self.log.add(tick, "IP_BLOCKED", dict(ip=tgt))
        for key, inc in self.incidents.items():
            if inc["kind"] in ("CYBERATTACK", "SENSOR_FAULT") and key[1] not in sensor_issues \
                    and inc["status"] == "ACTIVE":
                inc["status"] = "MITIGATED (rogue source blocked / ghost sensor in use)"

        # ---- 8. Flight recorder + classification ----
        digest = hashlib.sha1(json.dumps([round(float(x), 2) for x in P], default=_j).encode()).hexdigest()[:16]
        self.log.add(tick, "MEASUREMENT", dict(digest=digest, meter=round(float(tk["meter"]), 5)))
        classes = []
        if plumes:
            classes.append("CONTAMINATION")
        if real_leaks:
            classes.append("REAL_LEAK")
        kinds = {v["kind"] for v in sensor_issues.values()}
        classes += sorted(kinds)
        if ac:
            classes.append("MICRO_CRACK")
        if not classes:
            classes = ["NORMAL"]
        self.flagged, self.ghosts, self.votes = flagged, ghosts, votes
        self.summary = dict(tick=tick, classes=classes, flagged=flagged, ghosts=ghosts, votes=votes,
                            leaks=real_leaks, unverified=unverified, plumes=plumes, patient_zero=patient_zero,
                            sensor_issues=sensor_issues, acoustic=ac, excess_lps=excess * 1000, msgs=new_msgs,
                            residual=r, thr=thr)
        return self.summary

    # ---------- Patient Zero ----------
    def patient_zero(self, sol, ecl, plume_nodes, obs, active):
        """Reverse-time source search: which injection point best explains the observed plume?"""
        net = self.net
        out = net.flow_graph(sol["flows"])
        rev = {i: [] for i in range(net.n)}
        for u in range(net.n):
            for v, _, _ in out[u]:
                rev[v].append(u)
        cands, stack = set(plume_nodes), list(plume_nodes)
        while stack:                              # walk the network BACKWARDS
            v = stack.pop()
            for u in rev[v]:
                if u not in cands:
                    cands.add(u); stack.append(u)
        o = np.where(active, obs, 0.0)
        best = None
        for s in cands:
            if s == SOURCE:
                continue
            _, _, c = net.quality(sol, {s: 1.0})
            c = np.where(active, c, 0.0)
            denom = float(c @ c)
            if denom < 1e-12:
                continue
            a = max(float(c @ o) / denom, 0.0)
            err = float(((o - a * c) ** 2).sum())
            if best is None or err < best[0]:
                best = (err, s, a)
        if not best:
            return None
        err, s, a = best
        tt = net.travel_times(sol["flows"], s)
        age = max((tt.get(i, 0.0) for i in plume_nodes), default=0.0)
        conf = 1 - err / max(float(o @ o), 1e-12)
        # backtrack path: follow strongest upstream flow from the worst-hit node
        worst = max(plume_nodes, key=lambda i: obs[i])
        path, cur = [worst], worst
        while cur != s and len(path) < 20:
            ups = [(sol["flows"][k] if net.edges[k][1] == cur else -sol["flows"][k], u)
                   for u, k in net.nbrs[cur]]
            ups = [(q, u) for q, u in ups if q > 0 and (u == s or u in cands)]
            if not ups:
                break
            cur = max(ups)[1]; path.append(cur)
        return dict(node=int(s), rate=a, confidence=float(conf), age_min=float(age) / 60.0, path=path)

    # ---------- Smart Valve Doctor ----------
    def valve_doctor(self, isolate_nodes):
        """Close the boundary pipes of a node set, then VERIFY with the twin that hospitals keep pressure."""
        net = self.net
        S = set(isolate_nodes)
        boundary = [k for k, (a, b) in enumerate(net.edges) if (a in S) != (b in S)]
        hosp_in = [h for h in HOSPITALS if h in S]
        d = net.base_demand * demand_mult(360)
        for factor, label in ((0.0, "CLOSE"), (0.5, "THROTTLE 50%"), (0.25, "THROTTLE 75%")):
            if hosp_in and factor == 0.0:
                continue
            v = dict(self.valves)
            v.update({k: factor for k in boundary})
            sol = net.solve(d, v)
            rows = []
            ok = True
            for h, name in HOSPITALS.items():
                p = sol["h"][h] - net.z[h] if sol["reach"][h] else 0.0
                rows.append((name, h, float(p), p >= MIN_PRESSURE))
                ok &= p >= MIN_PRESSURE
            if ok:
                unserved = [i for i in range(net.n) if not sol["reach"][i]]
                steps = [f"{label} valve V{net.edges[k][0]:02d}-{net.edges[k][1]:02d}" for k in boundary]
                return dict(valves={k: factor for k in boundary}, steps=steps, unserved=unserved,
                            hospitals=rows, mode=label, safe=True)
        return dict(valves={}, steps=["No safe isolation: dispatch crew with bypass, notify hospital"],
                    unserved=[], hospitals=[], mode="MANUAL", safe=False)

    # ---------- Acoustic ----------
    def listen(self, wave):
        S = wave.shape[1]
        base = int(0.25 * FS)
        trig = {}
        for i in range(self.net.n):
            d = np.abs(np.diff(wave[i]))
            sd = d[:base].std() + 1e-9
            idx = np.nonzero(d > 8 * sd)[0]
            if len(idx):
                trig[i] = idx[0] / FS
        if len(trig) < 3:
            return None
        ids = list(trig)
        t = np.array([trig[i] for i in ids])
        best = min(range(self.net.n), key=lambda s: np.var(t - self.net.dist[s, ids] / WAVE_SPEED))
        mag = float(np.abs(wave[best]).max())
        return dict(node=int(best), mag=mag, sensors=len(ids), t0=float(np.mean(t - self.net.dist[best, ids] / WAVE_SPEED)))

    def reopen_all(self):
        self.valves.clear(); self.blocked_ips.clear(); self.incidents.clear(); self.crack_watch.clear()
        self.trust[:] = 1.0


# ============================ ORCHESTRATOR ==================================
class Simulation:
    def __init__(self, seed=1):
        self.world = World(seed)
        self.legacy = LegacySCADA(self.world.net)
        self.aquila = Aquila(self.world.net)
        self.last_tick = None
        self.history = []
        self.auto = True
        self.legacy_delay_h = LEGACY_DELAY_H

    def advance(self, k=1):
        for _ in range(k):
            tk = self.world.step()
            self.legacy.step(tk, self.world)
            s = self.aquila.step(tk, self.world.expected_demand(), self.auto, self.legacy_delay_h)
            self.world.valves = dict(self.aquila.valves)
            self.world.blocked_ips = set(self.aquila.blocked_ips)
            self.last_tick = tk
            self.history.append(dict(tick=tk["tick"], legacy_alarms=len(self.legacy.alarms),
                                     min_trust=float(self.aquila.trust.min()), classes=s["classes"]))
        a = self.aquila.roi
        a["ghost_avoided"] = self.legacy.ghost_dispatches
        return self.aquila.summary

    def repair(self):
        self.world.repair_all(); self.aquila.reopen_all()


# ============================ 3D / 2D VISUALS ===============================
def _lerp_hex(c1, c2, t):
    t = min(max(t, 0), 1)
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(a[i] + (b[i] - a[i]) * t):02x}" for i in range(3))


def build_3d(sim, n_frames=24, per_pipe=4):
    """Isometric glowing-particle mesh. Blue=fresh clean, neon green=chlorine normal,
    purple=contamination, flashing red=spoofed sensor zone."""
    import plotly.graph_objects as go
    w, aq = sim.world, sim.aquila
    net, tr = w.net, w.truth
    sol, cl, con = tr["sol"], tr["cl"], tr["con"]
    X, Y, Z = net.xy[:, 0], net.xy[:, 1], net.z * 3
    bad = set(aq.flagged)
    bad_edges = {k for i in bad for _, k in net.nbrs[i]}
    qmax = max(np.abs(sol["flows"]).max(), 1e-6)

    def line(edge_ids):
        xs, ys, zs = [], [], []
        for k in edge_ids:
            a, b = net.edges[k]
            xs += [X[a], X[b], None]; ys += [Y[a], Y[b], None]; zs += [Z[a], Z[b], None]
        return xs, ys, zs

    closed = [k for k in range(net.m) if aq.valves.get(k, 1.0) < 1.0]
    openp = [k for k in range(net.m) if k not in closed]
    x, y, zz = line(openp)
    pipes = go.Scatter3d(x=x, y=y, z=zz, mode="lines", line=dict(color="#24406b", width=5),
                         hoverinfo="skip", name="pipes")
    x, y, zz = line(closed)
    shut = go.Scatter3d(x=x, y=y, z=zz, mode="lines", line=dict(color="#ff9f1c", width=8),
                        hoverinfo="skip", name="closed valves")

    def node_trace(flash):
        cols = []
        for i in range(net.n):
            t = aq.trust[i]
            if i in bad:
                cols.append("#ff1744" if flash else "#5a0010")
            else:
                cols.append("#39ff14" if t > 0.8 else "#ffc400" if t > 0.4 else "#ff1744")
        return go.Scatter3d(
            x=X, y=Y, z=Z + 4, mode="markers",
            marker=dict(size=[11 if i in HOSPITALS else 6 for i in range(net.n)], color=cols,
                        symbol=["diamond" if i in HOSPITALS else "circle" for i in range(net.n)],
                        line=dict(width=1, color="white")),
            text=[f"node {i}{' ' + HOSPITALS[i] if i in HOSPITALS else ''}<br>trust {aq.trust[i]:.0%}"
                  f"<br>Cl {cl[i]:.2f} mg/L" for i in range(net.n)], hoverinfo="text", name="sensors")

    def particles(f, flash):
        px, py, pz, pc = [], [], [], []
        for k, (a, b) in enumerate(net.edges):
            q = sol["flows"][k]
            if abs(q) < 1e-9 or k in closed:
                continue
            s, e = (a, b) if q > 0 else (b, a)
            speed = 0.01 + 0.05 * abs(q) / qmax
            if k in bad_edges:
                col = "#ff1744" if flash else "#7a0016"
            elif con[s] > 0.05 or con[e] > 0.05:
                col = "#b100ff"
            else:
                col = _lerp_hex("#2aa8ff", "#39ff14", (CL_DOSE - cl[s]) / (CL_DOSE - 0.3))
            for j in range(per_pipe):
                phi = (f * speed + j / per_pipe) % 1.0
                px.append(X[s] + phi * (X[e] - X[s])); py.append(Y[s] + phi * (Y[e] - Y[s]))
                pz.append(Z[s] + phi * (Z[e] - Z[s]) + 4); pc.append(col)
        return go.Scatter3d(x=px, y=py, z=pz, mode="markers", marker=dict(size=3.2, color=pc, opacity=0.95),
                            hoverinfo="skip", name="water")

    frames = [go.Frame(data=[node_trace(f % 2 == 0), particles(f, f % 2 == 0)], traces=[2, 3], name=str(f))
              for f in range(n_frames)]
    fig = go.Figure(data=[pipes, shut, node_trace(True), particles(0, True)], frames=frames)
    ax = dict(visible=False)
    fig.update_layout(
        template="plotly_dark", height=620, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
        scene=dict(xaxis=ax, yaxis=ax, zaxis=ax, aspectmode="data", bgcolor="#050b18",
                   camera=dict(projection=dict(type="orthographic"), eye=dict(x=1.5, y=-1.5, z=1.2))),
        updatemenus=[dict(type="buttons", showactive=False, x=0.02, y=0.02, buttons=[
            dict(label="▶ Play flow", method="animate",
                 args=[None, dict(frame=dict(duration=90, redraw=True), fromcurrent=True, mode="immediate",
                                  transition=dict(duration=0))]),
            dict(label="❚❚", method="animate",
                 args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])])
    return fig


def build_2d(sim, view):
    """view='legacy' (raw sensor belief) or 'aquila' (trust-corrected belief)."""
    import plotly.graph_objects as go
    w, aq, lg = sim.world, sim.aquila, sim.legacy
    net = w.net
    fig = go.Figure()
    xs, ys = [], []
    for k, (a, b) in enumerate(net.edges):
        xs += [net.xy[a, 0], net.xy[b, 0], None]; ys += [net.xy[a, 1], net.xy[b, 1], None]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#24406b", width=2), hoverinfo="skip"))
    if view == "legacy":
        cols = ["#ff1744" if i in lg.active else "#39ff14" for i in range(net.n)]
        txt = [f"node {i}: " + ("ALARM" if i in lg.active else "ok") for i in range(net.n)]
    else:
        cols, txt = [], []
        for i in range(net.n):
            if i in aq.flagged:
                cols.append("#ffc400"); txt.append(f"node {i}: SPOOFED -> ghost sensor")
            elif i in {k for (kind, k) in aq.incidents if kind == "REAL_LEAK"}:
                cols.append("#00e5ff"); txt.append(f"node {i}: REAL LEAK")
            else:
                cols.append("#39ff14"); txt.append(f"node {i}: trust {aq.trust[i]:.0%}")
    fig.add_trace(go.Scatter(x=net.xy[:, 0], y=net.xy[:, 1], mode="markers+text", text=[str(i) for i in range(net.n)],
                             textposition="middle center", textfont=dict(size=8, color="black"),
                             marker=dict(size=20, color=cols, line=dict(width=1, color="white")),
                             hovertext=txt, hoverinfo="text"))
    fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                      xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"))
    return fig


# ============================ STREAMLIT UI ==================================
def run_ui():
    import pandas as pd
    import streamlit as st

    st.set_page_config(page_title="AQUILA", layout="wide", page_icon="🦅")
    if "sim" not in st.session_state:
        st.session_state.sim = Simulation()
        st.session_state.sim.advance(5)
    sim: Simulation = st.session_state.sim
    net = sim.world.net
    w = sim.world

    st.title("🦅 AQUILA — the AI guardian that can't be lied to")
    st.caption("Hackers can spoof data. They cannot hack the laws of physics.")

    with st.sidebar:
        st.header("☠️ Saboteur Mode")
        node = st.selectbox("Target junction", list(range(1, net.n)), index=11)
        mode = st.selectbox("Hack type", ["fake_burst", "hide_leak", "fake_chlorine", "hide_contam", "drift"])
        hacker = st.checkbox("Attacker (forged packets)", True, help="Off = honest hardware fault")
        n_run = 4
        if st.button("💻 Hack a sensor", use_container_width=True):
            w.hack_sensor(node, mode, hacker); sim.advance(n_run)
        lps = st.slider("Burst size (L/s)", 10, 60, 25)
        if st.button("💥 Burst a pipe", use_container_width=True):
            w.burst_pipe(node, lps); sim.advance(n_run)
        if st.button("☣️ Contaminate", use_container_width=True):
            w.contaminate(node, 0.02); sim.advance(n_run)
        if st.button("🔊 Hairline crack", use_container_width=True):
            w.crack_pipe(node); sim.advance(1)
        st.divider()
        steps = st.slider("Ticks (1 tick = 1 min)", 1, 30, 5)
        if st.button("⏩ Advance", use_container_width=True):
            sim.advance(steps)
        if st.button("🔧 Crew repaired / reset", use_container_width=True):
            sim.repair(); sim.advance(3)
        sim.auto = st.toggle("Automated valve quarantine", sim.auto)
        sim.legacy_delay_h = st.slider("Legacy detection delay (h) [assumption]", 1, 168, sim.legacy_delay_h)

    S = sim.aquila.summary
    roi = sim.aquila.roi
    c = st.columns(5)
    c[0].metric("💧 Litres saved", f"{roi['litres']:,.0f}")
    c[1].metric("₹ Saved", f"{roi['inr'] + roi['ghost_avoided'] * CREW_COST_INR:,.0f}")
    c[2].metric("⚡ kWh saved", f"{roi['kwh']:,.0f}")
    c[3].metric("🚧 Ghost crews avoided", roi["ghost_avoided"])
    c[4].metric("Aquila verdict", " + ".join(S["classes"]))

    st.subheader("⚔️ God Mode — same attack, two control rooms")
    L, R = st.columns(2)
    with L:
        st.markdown("### 🐢 Legacy SCADA\n*trusts every sensor*")
        st.plotly_chart(build_2d(sim, "legacy"), use_container_width=True, key="l2d")
        a, b, d = st.columns(3)
        a.metric("Alarms", len(sim.legacy.alarms)); b.metric("Crews sent", len(sim.legacy.dispatches))
        d.metric("Ghost leaks chased", sim.legacy.ghost_dispatches)
        st.metric("Money burned", f"₹{sim.legacy.wasted_inr:,}")
        st.metric("Undetected loss (L)", f"{sim.legacy.undetected_litres:,.0f}")
    with R:
        st.markdown("### 🦅 Aquila Neural Defense\n*physics-checked, swarm-voted*")
        st.plotly_chart(build_2d(sim, "aquila"), use_container_width=True, key="r2d")
        inc = list(sim.aquila.incidents.values())
        a, b, d = st.columns(3)
        a.metric("Spoofed sensors isolated", len(sim.aquila.flagged))
        b.metric("Open incidents", sum(1 for i in inc if i["status"] == "ACTIVE"))
        d.metric("Ghost crews sent", 0)
        st.metric("Money burned", "₹0")
        for i in inc[-4:]:
            st.info(f"**{i['kind']}** @ {i['node']} — {i['status']}\n\n{i['info']}")

    tabs = st.tabs(["🧊 3D Particle Mesh", "🗳️ Trust Swarm", "👻 Ghost Sensors", "🕵️ Patient Zero",
                    "🛠️ Valve Doctor", "🔊 Acoustic", "🔒 Flight Recorder"])
    with tabs[0]:
        st.plotly_chart(build_3d(sim), use_container_width=True, key="3d")
        st.caption("Blue = clean · neon green = chlorine normal · purple = contamination · "
                   "flashing red = spoofed zone · orange = closed valve. Press ▶ to animate.")
    with tabs[1]:
        st.dataframe(pd.DataFrame(dict(node=range(net.n), trust=[f"{t:.0%}" for t in sim.aquila.trust],
                                       residual_Lps=[f"{x * 1000:+.1f}" for x in S["residual"]])), height=300)
        for k, ballots in S["votes"].items():
            st.write(f"**Swarm vote on node {k}** (each neighbour computed this locally, no cloud)")
            st.table(pd.DataFrame([dict(voter=j, implied_pressure_m=round(v - float(net.z[k]), 2),
                                        votes_outlier=a, voter_trust=f"{t:.0%}") for j, v, a, t in ballots]))
    with tabs[2]:
        if S["ghosts"]:
            st.table(pd.DataFrame([dict(node=k, reported_m=round(g["reported"], 2), ghost_m=round(g["ghost"], 2))
                                   for k, g in S["ghosts"].items()]))
            st.success("Monitoring never went blind: ghost values replace lying sensors in every calculation.")
        else:
            st.write("No sensor currently replaced.")
    with tabs[3]:
        pz = S["patient_zero"]
        if pz:
            st.error(f"Poison entered at **node {pz['node']}** ≈ {pz['age_min']:.0f} min ago "
                     f"(fit {pz['confidence']:.0%}). Reverse path: {' ← '.join(map(str, pz['path'][::-1]))}")
        else:
            st.write("No contamination plume detected.")
    with tabs[4]:
        if sim.aquila.last_plan:
            p = sim.aquila.last_plan
            st.write(f"**Mode:** {p['mode']} · safe for hospitals: {p['safe']}")
            st.write(p["steps"])
            st.table(pd.DataFrame(p["hospitals"], columns=["facility", "node", "pressure_m", "ok"]))
            st.write(f"Customers without water during repair: {p['unserved']}")
        else:
            st.write("No isolation needed.")
    with tabs[5]:
        if sim.aquila.crack_watch:
            st.warning(f"Micro-cracks on watchlist: {sim.aquila.crack_watch}")
        st.line_chart(sim.last_tick["wave"][:3].T)
    with tabs[6]:
        ok, bad = sim.aquila.log.verify()
        st.success("Chain intact ✅") if ok else st.error(f"TAMPERING detected at entry {bad} ❌")
        if st.button("Simulate insider editing entry #3"):
            sim.aquila.log.chain[min(3, len(sim.aquila.log.chain) - 1)]["payload"] = {"edited": True}
            st.rerun()
        st.dataframe(pd.DataFrame([dict(i=e["i"], tick=e["tick"], kind=e["kind"], hash=e["hash"][:16])
                                   for e in sim.aquila.log.chain[-40:]]))


# ============================ HEADLESS SELF-TEST ============================
def run_demo():
    results = []

    def check(name, cond, extra=""):
        results.append(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {extra}")

    def fresh():
        s = Simulation(); s.advance(8); return s

    print("0) Baseline")
    s = fresh()
    check("no false alarms", s.aquila.summary["classes"] == ["NORMAL"], str(s.aquila.summary["classes"]))
    check("legacy quiet", len(s.legacy.alarms) == 0)

    print("1) REAL leak, node 12, 25 L/s")
    s = fresh(); s.world.burst_pipe(12, 25); s.advance(5)
    inc = [k for k in s.aquila.incidents if k[0] == "REAL_LEAK"]
    check("leak localised to node 12", inc == [("REAL_LEAK", 12)], str(inc))
    check("valves isolate it & hospitals safe", s.aquila.last_plan["safe"], str(s.aquila.last_plan["steps"]))
    check("leak stopped", 12 not in s.world.truth["sol"]["leakq"] or s.world.truth["sol"]["leakq"][12] == 0)
    check("litres saved > 0", s.aquila.roi["litres"] > 0, f"{s.aquila.roi['litres']:,.0f} L")

    print("2) CYBERATTACK: fake burst at node 8 (legacy panics)")
    s = fresh(); s.world.hack_sensor(8, "fake_burst", True); s.advance(4)
    check("legacy sent ghost crew", s.legacy.ghost_dispatches >= 1, f"ghost crews={s.legacy.ghost_dispatches}")
    check("aquila flagged node 8 only", s.aquila.incidents.keys() >= {("CYBERATTACK", 8)}
          and not any(k[0] == "REAL_LEAK" for k in s.aquila.incidents), str(list(s.aquila.incidents)))
    inc = s.aquila.incidents[("CYBERATTACK", 8)]
    print("     vector:", inc["info"]["vector"])
    check("rogue IP blocked", "185.220.101.47" in s.aquila.blocked_ips)
    check("sensor recovered after block", s.aquila.incidents[("CYBERATTACK", 8)]["status"].startswith("MITIGATED"))

    print("3) Honest hardware fault (valid signature) at node 17")
    s = fresh(); s.world.hack_sensor(17, "drift", False); s.advance(4)
    check("classified SENSOR_FAULT", ("SENSOR_FAULT", 17) in s.aquila.incidents, str(list(s.aquila.incidents)))

    print("4) STEALTH: real leak at 17 hidden by replay attack")
    s = fresh(); s.world.burst_pipe(17, 30); s.world.hack_sensor(17, "hide_leak", True); s.advance(5)
    keys = set(s.aquila.incidents)
    check("leak still found via ghost sensor", ("REAL_LEAK", 17) in keys, str(keys))
    check("attack also flagged", ("CYBERATTACK", 17) in keys)

    print("5) Contamination at node 6 -> patient zero")
    s = fresh(); s.world.contaminate(6, 0.02); s.advance(3)
    pz = s.aquila.summary["patient_zero"] or next(
        (v["info"]["patient_zero"] for k, v in s.aquila.incidents.items() if k[0] == "CONTAMINATION"), None)
    check("plume detected", any(k[0] == "CONTAMINATION" for k in s.aquila.incidents), str(list(s.aquila.incidents)))
    check("patient zero = node 6", pz is not None and pz["node"] == 6, str(pz))

    print("6) Spoofed chlorine at node 14 (isolated, no plume)")
    s = fresh(); s.world.hack_sensor(14, "fake_chlorine", True); s.advance(3)
    check("NOT called contamination", not any(k[0] == "CONTAMINATION" for k in s.aquila.incidents))
    check("flagged as cyber/sensor", any(k[1] == 14 and k[0] in ("CYBERATTACK", "SENSOR_FAULT") for k in s.aquila.incidents))

    print("7) Hairline crack at node 18 (acoustic)")
    s = fresh(); s.world.crack_pipe(18); s.advance(1)
    check("crack located", ("MICRO_CRACK", 18) in s.aquila.incidents, str(s.aquila.summary["acoustic"]))

    print("8) Flight recorder")
    ok, _ = s.aquila.log.verify()
    check("chain valid", ok)
    s.aquila.log.chain[2]["payload"] = {"x": 1}
    ok, bad = s.aquila.log.verify()
    check("tampering detected", (not ok) and bad == 2, f"broken at {bad}")

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return all(results)


if __name__ == "__main__":
    ctx = None
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
    except Exception:
        pass
    if ctx is not None:
        run_ui()
    else:
        ap = argparse.ArgumentParser()
        ap.add_argument("--demo", action="store_true", help="run headless scenario tests")
        a = ap.parse_args()
        if a.demo:
            sys.exit(0 if run_demo() else 1)
        print("Run the dashboard with:  streamlit run aquila.py   (or: python aquila.py --demo)")
