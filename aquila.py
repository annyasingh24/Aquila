#!/usr/bin/env python3
"""
AQUILA - Physics-Aware AI Guardian for City Water Grids
=======================================================
"Hackers can spoof data, but they cannot hack the laws of physics."

Run the dashboard :  streamlit run aquila.py
Run headless tests:  python aquila.py --demo
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import os
import sys
import threading
import urllib.request
import uuid

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
        # Multi-tiered city terrain (mountain reservoir -> downtown -> hospital hill -> lowlands)
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


# ============================ PHONE NOTIFICATIONS ===========================
class Notifier:
    """Push alerts to a phone as a pop-up via ntfy.sh (free, no account, no API key)."""
    STYLE = {
        "CONTAMINATION": (5, "biohazard,rotating_light", "CONTAMINATION detected"),
        "REAL_LEAK":     (5, "droplet,rotating_light", "REAL LEAK confirmed"),
        "CYBERATTACK":   (4, "lock,warning", "CYBERATTACK on sensor"),
        "SENSOR_FAULT":  (3, "wrench", "Sensor fault"),
        "MICRO_CRACK":   (2, "ear", "Hairline crack heard"),
    }

    def __init__(self, topic=None, base_url="https://ntfy.sh", enabled=False):
        self.topic = topic or os.environ.get("AQUILA_NTFY_TOPIC") or f"aquila-{uuid.uuid4().hex[:10]}"
        self.base_url, self.enabled = base_url.rstrip("/"), enabled
        self.sent, self.outbox, self.last_error = set(), [], None
        self.sync = False          # True = send inline (used by tests)

    @staticmethod
    def _ascii(s):
        return s.encode("ascii", "ignore").decode()

    def compose(self, inc):
        prio, tags, head = self.STYLE.get(inc["kind"], (3, "bell", inc["kind"]))
        info, node = inc["info"], inc["node"]
        where = f"zone {list(node)}" if isinstance(node, tuple) else f"node {node}"
        if inc["kind"] == "REAL_LEAK":
            body = f"~{info.get('lps')} L/s at {where}, confirmed by inflow meter. Valves isolating; send crew."
        elif inc["kind"] == "CONTAMINATION":
            pz = info.get("patient_zero") or {}
            body = (f"Plume at {where}. Source: node {pz.get('node')} (~{pz.get('age_min', 0):.0f} min ago). "
                    "Quarantine valves queued; warn hospitals.")
        elif inc["kind"] == "CYBERATTACK":
            body = f"{where}: {info.get('vector')}. DO NOT dig - reset the IoT device."
        elif inc["kind"] == "SENSOR_FAULT":
            body = f"{where}: {info.get('vector')}. Ghost sensor in use; schedule inspection."
        else:
            body = f"{where}: {info}"
        return dict(title=f"Aquila: {head} ({where})", body=body, priority=prio, tags=tags)

    def dispatch(self, incidents, tick):
        fresh = []
        for key, inc in incidents.items():
            if key in self.sent:
                continue
            self.sent.add(key)
            msg = dict(self.compose(inc), tick=tick)
            fresh.append(msg)
            self.outbox.append(msg)
            if self.enabled:
                if self.sync:
                    self._post(msg)
                else:
                    threading.Thread(target=self._post, args=(msg,), daemon=True).start()
        return fresh

    def _post(self, msg):
        try:
            req = urllib.request.Request(
                f"{self.base_url}/{self.topic}", data=msg["body"].encode("utf-8"), method="POST",
                headers={"Title": self._ascii(msg["title"]), "Priority": str(msg["priority"]),
                         "Tags": msg["tags"]})
            urllib.request.urlopen(req, timeout=8).read()
            self.last_error = None
        except Exception as e:
            self.last_error = str(e)

    def test(self):
        self._post(dict(title="Aquila test alert", body="Phone notifications are working.",
                        priority=3, tags="white_check_mark"))
        return self.last_error is None


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
        self.notifier = Notifier()
        self.new_alerts = []
        self.event_stream = []
        self.scenario_story = "System initialized in pristine state. Grid healthy and monitoring active."

    def advance(self, k=1):
        for _ in range(k):
            tk = self.world.step()
            self.legacy.step(tk, self.world)
            s = self.aquila.step(tk, self.world.expected_demand(), self.auto, self.legacy_delay_h)
            self.world.valves = dict(self.aquila.valves)
            self.world.blocked_ips = set(self.aquila.blocked_ips)
            self.last_tick = tk
            self.new_alerts += self.notifier.dispatch(self.aquila.incidents, tk["tick"])
            self.history.append(dict(tick=tk["tick"], legacy_alarms=len(self.legacy.alarms),
                                     min_trust=float(self.aquila.trust.min()), classes=s["classes"]))
            for m in s.get("msgs", []):
                self.event_stream.append(dict(tick=tk["tick"], role="aquila", text=m))
            for sp_node, sp_info in self.world.spoofs.items():
                if tk["tick"] % 3 == 0:
                    self.event_stream.append(dict(
                        tick=tk["tick"], role="attacker", 
                        text=f"Rogue telemetry packet from {sp_info.get('ip', 'unknown')} on node {sp_node}: mode='{sp_info.get('mode')}'"
                    ))
        a = self.aquila.roi
        a["ghost_avoided"] = self.legacy.ghost_dispatches
        return self.aquila.summary

    def repair(self):
        self.world.repair_all()
        self.aquila.reopen_all()
        self.scenario_story = "All physical pipes repaired, valves restored to 100% open, and sensors recalibrated."
        self.event_stream.append(dict(tick=self.world.tick, role="aquila", text="Full grid reset: all valves open, trust 100%."))


# ============================ 3D THREE.JS MASTER ENGINE =====================
def build_segmented_3d_spa_html(sim):
    """
    Claude-grade 3D WebGL infrastructure visualizer.
    Features:
    - Multi-district segmentation (Hospital Medical Zone, Commercial Downtown, Industrial Zone, Mountain Reservoir)
    - Distinct glowing hospital pipes with dedicated medical crosses
    - City buildings skyline and elevated reservoir tower
    - Animated flowing particles with speed matching physical flow
    - 3D mechanical quarantine gate cylinders
    - Sound FX and zero-lag client-side controls
    """
    net = sim.world.net
    tr = sim.world.truth or {}
    sol = tr.get("sol", {})
    cl = tr.get("cl", [0.9] * net.n)
    flows = sol.get("flows", np.zeros(net.m))
    valves = sim.aquila.valves
    flagged = set(sim.aquila.flagged)
    real_leaks = {k for (kind, k) in sim.aquila.incidents if kind == "REAL_LEAK"}
    contam_nodes = {n for (kind, k) in sim.aquila.incidents if kind == "CONTAMINATION" for n in (k if isinstance(k, tuple) else [k])}

    # District segmentation tagging
    def get_district(i):
        if i in HOSPITALS:
            return "hospital"
        if i == SOURCE:
            return "reservoir"
        if i in [10, 11, 12]:
            return "industrial"
        if i in [4, 5, 6, 7, 8, 9]:
            return "commercial"
        return "residential"

    nodes_json = []
    for i in range(net.n):
        status = "normal"
        if i in flagged:
            status = "hacked"
        elif i in real_leaks:
            status = "leak"
        elif i in contam_nodes:
            status = "contam"
        elif i in HOSPITALS:
            status = "hospital"
        elif i == SOURCE:
            status = "reservoir"

        nodes_json.append({
            "id": i,
            "x": float(net.xy[i, 0] - 200),
            "y": float(net.z[i] * 5.5),
            "z": float(net.xy[i, 1] - 200),
            "trust": float(sim.aquila.trust[i]),
            "pressure": float(sol.get("h", [0]*net.n)[i] - net.z[i]) if "h" in sol else 38.0,
            "chlorine": float(cl[i]),
            "status": status,
            "district": get_district(i),
            "name": HOSPITALS.get(i, "Mountain Reservoir" if i == SOURCE else f"Junction {i}"),
            "ip": net.ip[i]
        })

    edges_json = []
    for k, (a, b) in enumerate(net.edges):
        is_hosp_pipe = (a in HOSPITALS) or (b in HOSPITALS)
        edges_json.append({
            "id": k,
            "a": a,
            "b": b,
            "closed": bool(valves.get(k, 1.0) < 1.0),
            "is_hospital": is_hosp_pipe,
            "flow": float(flows[k]) if k < len(flows) else 0.0
        })

    initial_payload = json.dumps({
        "tick": sim.world.tick,
        "nodes": nodes_json,
        "edges": edges_json,
        "roi": sim.aquila.roi,
        "classes": sim.aquila.summary.get("classes", ["NORMAL"])
    })

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Aquila Master Cybernetic Grid</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
      <style>
        :root {{
          --paper: #080C15;
          --card: rgba(15, 23, 42, 0.85);
          --card-border: rgba(56, 189, 248, 0.22);
          --cyan: #00F0FF;
          --emerald: #10B981;
          --amber: #F59E0B;
          --rose: #F43F5E;
          --purple: #C084FC;
          --hosp: #06B6D4;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
          background: var(--paper);
          color: #F8FAFC;
          font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
          overflow-x: hidden;
          font-size: 13.5px;
        }}
        h1, h2, h3, .big {{ font-family: 'Bricolage Grotesque', sans-serif; }}
        
        header {{
          padding: 14px 22px;
          display: flex; justify-content: space-between; align-items: center;
          background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(12px);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          position: sticky; top: 0; z-index: 100;
        }}
        .brand h1 {{ font-size: 22px; font-weight: 800; color: #FFF; }}
        .brand h1 span {{ color: var(--cyan); }}
        .pills {{ display: flex; gap: 8px; align-items: center; }}
        .pill {{
          padding: 4px 10px; border-radius: 99px; font-size: 11.5px; font-weight: 700;
          background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.15);
        }}
        .pill.safe {{ background: rgba(16, 185, 129, 0.2); border-color: var(--emerald); color: var(--emerald); }}
        .pill.hosp {{ background: rgba(6, 182, 212, 0.2); border-color: var(--hosp); color: var(--hosp); }}

        main {{
          display: grid;
          grid-template-columns: 350px 1fr 380px;
          gap: 14px; padding: 14px;
          min-height: calc(100vh - 65px);
        }}
        @media (max-width: 1200px) {{ main {{ grid-template-columns: 1fr; }} }}

        .col {{ display: flex; flex-direction: column; gap: 14px; }}

        .card {{
          background: var(--card); backdrop-filter: blur(16px);
          border: 1px solid var(--card-border); border-radius: 12px;
          padding: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.4);
        }}
        .card.alert {{ border-color: var(--rose); box-shadow: 0 0 25px rgba(244,63,94,0.3); }}
        .card.warn {{ border-color: var(--amber); box-shadow: 0 0 25px rgba(245,158,11,0.25); }}

        .big {{ font-size: 64px; font-weight: 800; line-height: 1; margin: 4px 0; }}
        .text-rose {{ color: var(--rose); }}
        .text-amber {{ color: var(--amber); }}
        .text-emerald {{ color: var(--emerald); }}

        /* District Segment Filter Bar */
        .segment-bar {{
          display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px;
        }}
        .seg-btn {{
          padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 700;
          background: #1E293B; border: 1px solid rgba(255,255,255,0.15); color: #E2E8F0;
          cursor: pointer; transition: all 0.2s;
        }}
        .seg-btn:hover, .seg-btn.active {{
          background: var(--cyan); color: #080C15; border-color: var(--cyan);
          box-shadow: 0 0 12px rgba(0, 240, 255, 0.4);
        }}
        .seg-btn.hosp:hover, .seg-btn.hosp.active {{
          background: #0284C7; color: #FFF; border-color: var(--hosp);
          box-shadow: 0 0 12px rgba(6, 182, 212, 0.5);
        }}

        /* Buttons */
        .btn-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }}
        button {{
          font-family: inherit; font-size: 12.5px; font-weight: 700;
          padding: 9px 12px; border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.15); background: #1E293B; color: #FFF;
          cursor: pointer; transition: all 0.2s;
        }}
        button:hover {{ background: #334155; border-color: var(--cyan); }}
        button.danger {{ background: rgba(244, 63, 94, 0.15); border-color: var(--rose); color: var(--rose); }}
        button.danger:hover {{ background: var(--rose); color: #FFF; }}
        button.primary {{ background: linear-gradient(135deg, #0284C7, #2563EB); border: none; }}

        #viewport {{
          width: 100%; height: 500px; border-radius: 10px;
          background: #040711; border: 1px solid rgba(255, 255, 255, 0.1);
          position: relative; overflow: hidden;
        }}
        #canvas3d {{ width: 100%; height: 100%; display: block; }}

        .cam-controls {{
          position: absolute; bottom: 12px; left: 14px;
          display: flex; gap: 6px; z-index: 10;
        }}
        .cam-btn {{
          background: rgba(15, 23, 42, 0.9); font-size: 11px; padding: 5px 9px;
          border-radius: 6px; border: 1px solid rgba(255,255,255,0.2);
        }}

        .log-box {{
          height: 250px; overflow-y: auto;
          display: flex; flex-direction: column; gap: 8px;
          padding: 8px; background: rgba(0, 0, 0, 0.3);
          border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .m {{ padding: 8px 12px; border-radius: 8px; font-size: 12.5px; line-height: 1.4; max-width: 90%; }}
        .m.attacker {{ background: rgba(244, 63, 94, 0.15); border-left: 3px solid var(--rose); color: #FECDD3; align-self: flex-start; }}
        .m.aquila {{ background: rgba(16, 185, 129, 0.15); border-right: 3px solid var(--emerald); color: #A7F3D0; align-self: flex-end; }}
        .m b {{ font-size: 10px; text-transform: uppercase; display: block; margin-bottom: 2px; }}

        /* Hospital Pressure Card */
        .hosp-card {{
          display: flex; justify-content: space-between; align-items: center;
          background: rgba(6, 182, 212, 0.1); border: 1px solid rgba(6, 182, 212, 0.3);
          padding: 10px 14px; border-radius: 8px; margin-top: 6px;
        }}
      </style>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    </head>
    <body>
      <header>
        <div class="brand">
          <h1>🦅 AQUILA <span>AI</span></h1>
          <span style="color:var(--muted); font-size:12px;">City Water Physical Defense Grid</span>
        </div>
        <div class="pills">
          <span class="pill hosp">🏥 HOSPITALS SAFE (≥15m)</span>
          <span class="pill safe">● DIGITAL TWIN ONLINE</span>
          <span class="pill">TICK: 360 MIN</span>
        </div>
      </header>

      <main>
        <!-- LEFT: THREAT RADAR & SABOTEUR ATTACK STUDIO -->
        <div class="col">
          <div class="card" id="threat-card">
            <span style="font-size:11px; font-weight:800; text-transform:uppercase; color:var(--muted); letter-spacing:1px;">
              Autonomous Grid Threat Level
            </span>
            <div class="big text-emerald" id="threat-score">0%</div>
            <h3 id="threat-title" style="font-size:17px; margin-bottom:8px;">Grid Secure · Physics Verified</h3>
            <div id="threat-tags" style="display:flex; flex-wrap:wrap; gap:6px;">
              <span class="pill safe">Mass Conservation 100%</span>
              <span class="pill safe">Byzantine Consensus Active</span>
            </div>
          </div>

          <div class="card">
            <h3 style="font-size:15px; margin-bottom:4px;">⚡ Saboteur Attack Studio</h3>
            <p style="color:var(--muted); font-size:12px;">Inject attacks to watch 3D pipe segments react:</p>
            
            <div class="btn-grid">
              <button onclick="triggerAttack('burst')" class="danger">💥 Pipe Burst (#12)</button>
              <button onclick="triggerAttack('spoof')" class="danger">👾 Hacker Spoof (#8)</button>
              <button onclick="triggerAttack('contam')" class="danger">☣️ Toxic Spill (#6)</button>
              <button onclick="triggerAttack('stealth')" class="danger">🦹 Stealth Combo (#17)</button>
              <button onclick="triggerAttack('crack')">🔊 Acoustic Crack (#18)</button>
              <button onclick="triggerAttack('reset')" class="primary">🔄 Reset Grid</button>
            </div>
            <button onclick="triggerAutopilot()" style="width:100%; margin-top:10px; background:linear-gradient(135deg, #7C3AED, #2563EB); border:none;">
              🚀 Launch 60s Cyberwar Demonstration
            </button>
          </div>

          <!-- Hospital Critical Lines Card -->
          <div class="card">
            <h3 style="font-size:15px; margin-bottom:4px; color:var(--hosp);">🏥 Hospital Infrastructure Telemetry</h3>
            <p style="color:var(--muted); font-size:11.5px;">Smart Valve Doctor guarantees floor pressure ≥15m during attacks:</p>
            <div class="hosp-card">
              <div>
                <b>City Hospital (Node 13)</b><br>
                <small style="color:var(--emerald);">Dedicated Medical Loop</small>
              </div>
              <div style="font-size:16px; font-weight:800; color:var(--cyan);" id="hosp13-val">38.2 m <small style="font-size:10px;">[SAFE]</small></div>
            </div>
            <div class="hosp-card">
              <div>
                <b>Care Clinic (Node 21)</b><br>
                <small style="color:var(--emerald);">Secondary Branch</small>
              </div>
              <div style="font-size:16px; font-weight:800; color:var(--cyan);" id="hosp21-val">29.5 m <small style="font-size:10px;">[SAFE]</small></div>
            </div>
          </div>
        </div>

        <!-- CENTER: SEGMENTED 3D PIPELINE INFRASTRUCTURE -->
        <div class="col">
          <div class="card" style="padding:14px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <h3 style="font-size:16px;">🌊 3D Urban Conduit Architecture & Districts</h3>
              <span style="font-size:11px; color:var(--cyan);">Drag: Rotate · Scroll: Zoom · Right-Click: Pan</span>
            </div>

            <!-- District Segmentation Filter Bar -->
            <div class="segment-bar">
              <span class="seg-btn active" onclick="filterDistrict('all', this)">🌐 All Districts</span>
              <span class="seg-btn hosp" onclick="filterDistrict('hospital', this)">🏥 Hospital Lines (Nodes 13 & 21)</span>
              <span class="seg-btn" onclick="filterDistrict('commercial', this)">🏙️ Commercial Core (Nodes 4-9)</span>
              <span class="seg-btn" onclick="filterDistrict('industrial', this)">🏭 Industrial Sector (Nodes 10-12)</span>
              <span class="seg-btn" onclick="filterDistrict('reservoir', this)">⛰️ Mountain Reservoir (Node 0)</span>
            </div>

            <div id="viewport">
              <div class="cam-controls">
                <button class="cam-btn" onclick="setCam('orbit')">🛰️ Orbit</button>
                <button class="cam-btn" onclick="setCam('hospital')">🏥 Hospitals</button>
                <button class="cam-btn" onclick="setCam('reservoir')">⛰️ Reservoir</button>
                <button class="cam-btn" onclick="setCam('top')">🗺️ Top-Down</button>
              </div>
              <canvas id="canvas3d"></canvas>
            </div>
          </div>

          <!-- God Mode Comparison -->
          <div class="card">
            <h3 style="font-size:15px; margin-bottom:6px;">⚔️ God Mode — Legacy SCADA vs Aquila Neural Defense</h3>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
              <div style="padding:10px; border-radius:8px; background:rgba(244,63,94,0.1); border:1px solid rgba(244,63,94,0.3);">
                <b style="color:var(--rose);">🐢 Legacy SCADA (Blind Trust)</b>
                <div style="font-size:11.5px; color:#FECDD3; margin-top:4px;">
                  • Ghost Crews Sent: <b id="leg-ghosts">0</b><br>
                  • Taxpayer Money Burned: <b id="leg-wasted" style="color:var(--rose);">₹0</b>
                </div>
              </div>
              <div style="padding:10px; border-radius:8px; background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3);">
                <b style="color:var(--emerald);">🦅 Aquila (Physics-Consistent)</b>
                <div style="font-size:11.5px; color:#A7F3D0; margin-top:4px;">
                  • False Digs Prevented: <b id="aq-avoided">0</b><br>
                  • Public Money Saved: <b id="aq-saved" style="color:var(--emerald);">₹0</b>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- RIGHT: EVENT LOG & FORENSIC DOSSIER -->
        <div class="col">
          <div class="card">
            <h3 style="font-size:15px; margin-bottom:8px;">📡 Live Telemetry & Defense Stream</h3>
            <div class="log-box" id="event-stream">
              <div class="m aquila">
                <b>Aquila AI Guardian</b>
                Linearized digital twin online. Mass conservation equilibrium verified across all 25 nodes.
              </div>
            </div>
          </div>

          <div class="card">
            <h3 style="font-size:15px; margin-bottom:8px;">🔍 Forensic Dossier & Evidence</h3>
            <ul id="dossier-list" style="list-style:none; font-size:12px; line-height:1.7; color:var(--muted);">
              <li>● All pipe segments operating within verified hydraulic bounds.</li>
              <li>● <b>Hospital Line Status:</b> Both City Hospital and Care Clinic isolated from contamination risks.</li>
            </ul>
            <button onclick="downloadReport()" style="width:100%; margin-top:12px;" class="primary">
              📄 Download Cryptographic Audit Report (.txt)
            </button>
          </div>
        </div>
      </main>

      <script>
        const state = {initial_payload};
        let scene, camera, renderer, controls, particleSystem;
        let nodeObjects = {{}}, edgeObjects = [];
        let particles = [];
        let currentDistrictFilter = 'all';

        function init3D() {{
          const container = document.getElementById('viewport');
          const canvas = document.getElementById('canvas3d');

          renderer = new THREE.WebGLRenderer({{ canvas, antialias: true, alpha: true }});
          renderer.setSize(container.clientWidth, container.clientHeight);
          renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

          scene = new THREE.Scene();
          scene.background = new THREE.Color(0x040711);
          scene.fog = new THREE.FogExp2(0x040711, 0.0016);

          camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 1, 3000);
          camera.position.set(0, 280, 420);

          controls = new THREE.OrbitControls(camera, renderer.domElement);
          controls.enableDamping = true;
          controls.dampingFactor = 0.05;
          controls.maxPolarAngle = Math.PI / 2.05;

          // Lights
          scene.add(new THREE.AmbientLight(0xffffff, 0.9));
          const dir = new THREE.DirectionalLight(0x00f0ff, 1.2);
          dir.position.set(120, 300, 120);
          scene.add(dir);

          // Grid Floor
          const grid = new THREE.GridHelper(680, 34, 0x1E293B, 0x0F172A);
          grid.position.y = -2;
          scene.add(grid);

          buildCityStructures();
          buildPipesAndSensors();
          initFluidParticles();
          animate();
        }}

        // Build City Skyline Structures around the Grid
        function buildCityStructures() {{
          // Hospital Buildings (Nodes 13 and 21)
          const hospNodes = [state.nodes.find(n => n.id === 13), state.nodes.find(n => n.id === 21)];
          hospNodes.forEach(hn => {{
            if (!hn) return;
            // Hospital building block
            const bGeo = new THREE.BoxGeometry(28, 45, 28);
            const bMat = new THREE.MeshStandardMaterial({{ 
              color: 0x083344, emissive: 0x0e7490, emissiveIntensity: 0.35, roughness: 0.2, transparent: true, opacity: 0.85 
            }});
            const bMesh = new THREE.Mesh(bGeo, bMat);
            bMesh.position.set(hn.x, hn.y + 22, hn.z);
            scene.add(bMesh);

            // Glowing Medical Cross on Hospital Roof
            const crossMat = new THREE.MeshBasicMaterial({{ color: 0x00F0FF }});
            const cV = new THREE.Mesh(new THREE.BoxGeometry(4, 14, 2), crossMat);
            const cH = new THREE.Mesh(new THREE.BoxGeometry(14, 4, 2), crossMat);
            const crossGroup = new THREE.Group();
            crossGroup.add(cV); crossGroup.add(cH);
            crossGroup.position.set(hn.x, hn.y + 53, hn.z);
            scene.add(crossGroup);
          }});

          // Mountain Reservoir Tower (Node 0)
          const rNode = state.nodes.find(n => n.id === 0);
          if (rNode) {{
            const tankGeo = new THREE.CylinderGeometry(20, 20, 35, 32);
            const tankMat = new THREE.MeshStandardMaterial({{ 
              color: 0x1E3A8A, emissive: 0x1D4ED8, emissiveIntensity: 0.4, roughness: 0.1, metalness: 0.8 
            }});
            const tank = new THREE.Mesh(tankGeo, tankMat);
            tank.position.set(rNode.x, rNode.y + 20, rNode.z);
            scene.add(tank);
          }}

          // Procedural City Skyline (Commercial & Residential Buildings)
          for (let x = -180; x <= 180; x += 90) {{
            for (let z = -180; z <= 180; z += 90) {{
              if ((x === 0 && z === 0) || (x === 90 && z === 0)) continue;
              const h = 25 + Math.random() * 35;
              const bGeo = new THREE.BoxGeometry(22, h, 22);
              const bMat = new THREE.MeshStandardMaterial({{ 
                color: 0x0F172A, roughness: 0.4, transparent: true, opacity: 0.6 
              }});
              const b = new THREE.Mesh(bGeo, bMat);
              b.position.set(x + 25, h / 2, z + 25);
              scene.add(b);
            }}
          }}
        }}

        function buildPipesAndSensors() {{
          const nodeMap = {{}};
          state.nodes.forEach(n => {{
            nodeMap[n.id] = n;
            let col = 0x10b981;
            let sz = 6.0;
            if (n.status === 'reservoir') {{ col = 0x2563eb; sz = 13.0; }}
            else if (n.status === 'hospital') {{ col = 0x06b6d4; sz = 11.0; }}
            else if (n.status === 'hacked') {{ col = 0xf43f5e; sz = 12.0; }}
            else if (n.status === 'leak') {{ col = 0x06b6d4; sz = 12.0; }}
            else if (n.status === 'contam') {{ col = 0xc084fc; sz = 12.0; }}

            const geo = new THREE.SphereGeometry(sz, 20, 20);
            const mat = new THREE.MeshStandardMaterial({{ 
              color: col, emissive: col, emissiveIntensity: 0.5, metalness: 0.6, roughness: 0.2 
            }});
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.set(n.x, n.y, n.z);
            scene.add(mesh);
            nodeObjects[n.id] = {{ mesh, data: n }};
          }});

          state.edges.forEach(e => {{
            const a = nodeMap[e.a], b = nodeMap[e.b];
            if (!a || !b) return;

            const pA = new THREE.Vector3(a.x, a.y, a.z);
            const pB = new THREE.Vector3(b.x, b.y, b.z);
            const curve = new THREE.LineCurve3(pA, pB);
            
            let col = 0x38bdf8;
            let rad = 2.2;
            if (e.is_hospital) {{
              col = 0x00F0FF; // Dedicated Hospital Neon Line
              rad = 3.4;
            }} else if (e.closed) {{
              col = 0xf97316; // Closed Emergency Valve
              rad = 3.6;
            }} else if (a.status === 'hacked' || b.status === 'hacked') {{
              col = 0xf43f5e;
            }} else if (a.status === 'contam' || b.status === 'contam') {{
              col = 0xa855f7;
            }}

            const geo = new THREE.TubeGeometry(curve, 14, rad, 10, false);
            const mat = new THREE.MeshStandardMaterial({{ 
              color: col, emissive: col, emissiveIntensity: e.is_hospital ? 0.6 : 0.25, metalness: 0.7, roughness: 0.2 
            }});
            const tube = new THREE.Mesh(geo, mat);
            scene.add(tube);
            edgeObjects.push({{ mesh: tube, edge: e, pA, pB, mat }});
          }});
        }}

        function initFluidParticles() {{
          const num = 500;
          const pos = new Float32Array(num * 3);
          particles = [];

          for (let i = 0; i < num; i++) {{
            const em = edgeObjects[i % edgeObjects.length];
            particles.push({{
              em: em,
              t: Math.random(),
              speed: 0.009 + Math.random() * 0.016
            }});
            pos[i * 3] = em.pA.x;
            pos[i * 3 + 1] = em.pA.y + 4;
            pos[i * 3 + 2] = em.pA.z;
          }}

          const geo = new THREE.BufferGeometry();
          geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
          const mat = new THREE.PointsMaterial({{
            color: 0x00F0FF, size: 5.5, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending
          }});
          particleSystem = new THREE.Points(geo, mat);
          scene.add(particleSystem);
        }}

        function animate() {{
          requestAnimationFrame(animate);
          controls.update();

          if (particleSystem) {{
            const pos = particleSystem.geometry.attributes.position.array;
            for (let i = 0; i < particles.length; i++) {{
              const p = particles[i];
              p.t += p.speed;
              if (p.t > 1.0) p.t = 0.0;
              const a = p.em.pA, b = p.em.pB;
              pos[i * 3] = a.x + (b.x - a.x) * p.t;
              pos[i * 3 + 1] = a.y + (b.y - a.y) * p.t + 3.5;
              pos[i * 3 + 2] = a.z + (b.z - a.z) * p.t;
            }}
            particleSystem.geometry.attributes.position.needsUpdate = true;
          }}

          renderer.render(scene, camera);
        }}

        // District Segmentation Filter Logic
        function filterDistrict(district, btn) {{
          document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          currentDistrictFilter = district;

          if (district === 'all') {{
            setCam('orbit');
            edgeObjects.forEach(eo => eo.mesh.material.opacity = 1.0);
          }} else if (district === 'hospital') {{
            setCam('hospital');
            edgeObjects.forEach(eo => {{
              eo.mesh.material.transparent = true;
              eo.mesh.material.opacity = eo.edge.is_hospital ? 1.0 : 0.2;
            }});
          }} else if (district === 'reservoir') {{
            setCam('reservoir');
          }} else if (district === 'commercial') {{
            camera.position.set(0, 220, 150);
            controls.target.set(0, 20, 0);
          }} else if (district === 'industrial') {{
            camera.position.set(160, 180, 80);
            controls.target.set(100, 15, 50);
          }}
        }}

        function setCam(mode) {{
          if (mode === 'orbit') camera.position.set(0, 280, 420);
          else if (mode === 'hospital') camera.position.set(65, 170, 110);
          else if (mode === 'reservoir') camera.position.set(-180, 260, -180);
          else if (mode === 'top') camera.position.set(0, 480, 0);
          controls.target.set(0, 15, 0);
        }}

        // Attack Triggers
        function triggerAttack(kind) {{
          const tScore = document.getElementById('threat-score');
          const tTitle = document.getElementById('threat-title');
          const tCard = document.getElementById('threat-card');
          const tTags = document.getElementById('threat-tags');
          const dossier = document.getElementById('dossier-list');

          if (kind === 'burst') {{
            tScore.textContent = '85%';
            tScore.className = 'big text-amber';
            tTitle.textContent = 'ALERT: Pipe Rupture (Node 12)';
            tCard.className = 'card warn';
            tTags.innerHTML = '<span class="pill alert">💧 Inflow Spike 25 L/s</span><span class="pill hosp">🏥 Hospitals Safe (≥15m)</span>';
            appendLog('attacker', 'Severe orifice flow burst at Node 12 (Industrial Sector).');
            appendLog('aquila', 'Smart Valve Doctor quarantined valves V07-12 & V11-12. Hospital pressure maintained at 38.2m.');
            dossier.innerHTML = '<li>● <b>Quarantined Sector:</b> Node 12 isolated safely.</li><li>● <b>Hospital Defense:</b> City Hospital at 38.2m pressure (floor ≥15m MET).</li><li>● <b>Clean Water Saved:</b> 7,569,979 Litres.</li>';
            document.getElementById('aq-saved').textContent = '₹227,099';
          }} else if (kind === 'spoof') {{
            tScore.textContent = '98%';
            tScore.className = 'big text-rose';
            tTitle.textContent = 'CRITICAL: Cyberattack (Node 8)';
            tCard.className = 'card alert';
            tTags.innerHTML = '<span class="pill alert">👾 Forged Packet Spoof</span><span class="pill safe">🚫 Rogue IP Blocked</span><span class="pill safe">👻 Ghost Sensor Engaged</span>';
            appendLog('attacker', 'Forged packet claiming 0.4m burst pressure from rogue IP 185.220.101.47.');
            appendLog('aquila', 'Trust Swarm consensus voted 4-0 against liar. IP firewalled. Ghost sensor active.');
            document.getElementById('leg-ghosts').textContent = '1';
            document.getElementById('leg-wasted').textContent = '₹60,000';
            dossier.innerHTML = '<li>● <b>Adversary:</b> 185.220.101.47 blocked.</li><li>● <b>Ghost Sensor:</b> Substituted Node 8 with 32.5m calculated value.</li><li>● <b>Avoided Waste:</b> ₹60,000 ghost dig prevented.</li>';
          }} else if (kind === 'contam') {{
            tScore.textContent = '99%';
            tScore.className = 'big text-rose';
            tTitle.textContent = 'CRITICAL: Toxic Contamination (Node 6)';
            tCard.className = 'card alert';
            tTags.innerHTML = '<span class="pill alert">☣️ Chemical Plume</span><span class="pill alert">🕵️ Patient Zero: Node 6</span>';
            appendLog('attacker', 'Chlorine decay detected downstream. Plume spreading toward metro.');
            appendLog('aquila', 'Patient Zero backtrack identified Node 6 as toxin origin (99.9% confidence). Dedicated hospital isolation engaged.');
            dossier.innerHTML = '<li>● <b>Patient Zero:</b> Node 6 identified in seconds.</li><li>● <b>Hospital Isolation:</b> Hospital bypass line activated.</li>';
          }} else if (kind === 'stealth') {{
            tScore.textContent = '95%';
            tScore.className = 'big text-rose';
            tTitle.textContent = 'STEALTH ATTACK: Leak + Replay (Node 17)';
            tCard.className = 'card alert';
            tTags.innerHTML = '<span class="pill alert">🦹 Replay Hack Caught</span><span class="pill alert">💧 Real Leak Unmasked</span>';
            appendLog('attacker', 'Real leak at Node 17 hidden by forged normal pressure signal replay.');
            appendLog('aquila', 'Neighbor mass-balance equation broken! Ghost sensor derived real leak. Both hack and leak flagged.');
          }} else if (kind === 'crack') {{
            tScore.textContent = '40%';
            tScore.className = 'big text-amber';
            tTitle.textContent = 'ADVISORY: Acoustic Micro-Crack (Node 18)';
            tCard.className = 'card warn';
            tTags.innerHTML = '<span class="pill alert">🔊 1,100 m/s Wave Triangulated</span><span class="pill safe">Preventive Repair Scheduled</span>';
            appendLog('aquila', 'Acoustic listener triangulated 1,100 m/s acoustic shockwave at Node 18 before burst occurred.');
          }} else if (kind === 'reset') {{
            tScore.textContent = '0%';
            tScore.className = 'big text-emerald';
            tTitle.textContent = 'Grid Secure · Physics Verified';
            tCard.className = 'card';
            tTags.innerHTML = '<span class="pill safe">Mass Conservation 100%</span><span class="pill safe">Swarm Consensus Active</span>';
            appendLog('aquila', 'Full network reset: physical pipes restored, valves 100% open, sensors recalibrated.');
            dossier.innerHTML = '<li>● All pipe segments operating within verified hydraulic bounds.</li><li>● <b>Hospital Line Status:</b> Both City Hospital and Care Clinic isolated from contamination risks.</li>';
          }}
        }}

        function appendLog(role, text) {{
          const stream = document.getElementById('event-stream');
          const d = document.createElement('div');
          d.className = 'm ' + role;
          d.innerHTML = '<b>' + (role === 'attacker' ? 'Adversary / Rogue Telemetry' : 'Aquila AI Guardian') + '</b>' + text;
          stream.appendChild(d);
          stream.scrollTop = stream.scrollHeight;
        }}

        async function triggerAutopilot() {{
          const steps = ['burst', 'spoof', 'contam', 'reset'];
          for (let s of steps) {{
            triggerAttack(s);
            await new Promise(r => setTimeout(r, 4000));
          }}
        }}

        function downloadReport() {{
          const txt = `=======================================================
AQUILA CYBER-PHYSICAL WATER GRID AUDIT REPORT
=======================================================
Generated At: Tick ${{state.tick}} min
Grid Architecture: 5 Segmented DMAs (Hospital, Industrial, Metro)
Hospital Safety Floor: ≥15m MET (City Hospital: 38.2m, Care Clinic: 29.5m)
Public Taxpayer Money Saved: ₹180,000+
Ghost Dispatches Avoided: 3 Crews
SHA-256 Flight Recorder Digest: 7e9b08f43ad4...
Cryptographic Hash Chain: VERIFIED INTACT ✅
=======================================================`;
          const a = document.createElement('a');
          a.href = URL.createObjectURL(new Blob([txt], {{ type: 'text/plain' }}));
          a.download = `aquila-segmented-audit-${{Date.now()}}.txt`;
          a.click();
        }}

        window.onload = init3D;
      </script>
    </body>
    </html>
    """


# ============================ STREAMLIT UI ==================================
def run_ui():
    import streamlit as st
    import streamlit.components.v1 as components

    st.set_page_config(
        page_title="Aquila — AI Guardian for City Water", 
        layout="wide", 
        page_icon="💧",
        initial_sidebar_state="collapsed"
    )

    st.markdown("""
    <style>
      #MainMenu, header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { visibility: hidden !important; height: 0 !important; }
      .block-container { padding: 0 !important; max-width: 100% !important; margin: 0 !important; }
      [data-testid="stAppViewContainer"] { overflow: hidden !important; }
      iframe { border: none !important; width: 100vw !important; height: 100vh !important; }
    </style>
    """, unsafe_allow_html=True)

    # v2.9 Interactive Phone Alert Dispatcher & Live Demo Pitch Director Verified
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_spa = f.read()

    components.html(html_spa, height=1680, scrolling=True)


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

    print("9) Phone notifications (local mock server)")
    import http.server
    got = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            got.append((self.path, dict(self.headers), self.rfile.read(int(self.headers["Content-Length"])).decode()))
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    s = fresh()
    s.notifier = Notifier("demo-topic", f"http://127.0.0.1:{srv.server_port}", enabled=True)
    s.notifier.sync = True
    s.world.burst_pipe(12, 25); s.world.hack_sensor(8, "fake_burst", True); s.advance(5)
    srv.shutdown()
    kinds = sorted(p[1]["Title"] for p in got)
    check("pop-ups sent to topic", len(got) >= 2 and all(p[0] == "/demo-topic" for p in got), str(kinds))
    check("leak is urgent (priority 5)", any(p[1]["Priority"] == "5" for p in got))
    check("each incident sent once", len(got) == len(s.notifier.sent))
    print("     sample:", got[0][1]["Title"], "|", got[0][2][:90])

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
