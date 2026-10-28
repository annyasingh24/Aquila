"""
AQUILA Autonomous Physics-Checked Defense Engine
================================================
Implements Federated Sensor Trust Swarm, Ghost Sensor Math Engine,
Four-Way Threat Classifier, Smart Valve Doctor, and Patient Zero Backtracking.
"""

import hashlib
import json
import math
import numpy as np

from backend.config import (
    SOURCE, HOSPITALS, MIN_PRESSURE, DT, P_NOISE, VOTE_TOL,
    LEGACY_DELAY_H, ENERGY_KWH_PER_M3, WATER_INR_PER_M3, INR_PER_KWH,
    FS, WAVE_SPEED, json_sanitize
)
from backend.digital_twin import demand_mult
from backend.flight_recorder import AuditLog
from backend.simulation import PhysicalWorld
from backend.legacy_scada import LegacySCADA
from backend.notifier import Notifier


class Aquila:
    """Master physics guardian engine."""

    def __init__(self, net):
        self.net = net
        n = net.n
        self.trust = np.ones(n)
        self.valves = {}
        self.blocked_ips = set()
        self.log = AuditLog()
        self.incidents = {}
        self.ghosts = {}
        self.flagged = []
        self.votes = {}
        self.roi = dict(litres=0.0, kwh=0.0, inr=0.0, ghost_avoided=0, events=0)
        self.summary = {}
        self.crack_watch = {}
        self.last_plan = None
        self._pending = []

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
            res[k] = dict(
                frac=frac,
                ballots=ballots,
                ghost=float(np.median([b[1] for b in ballots])),
                strength=abs(r[k]) / thr[k]
            )
        return res

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

        # 1. Federated trust swarm: greedy consensus eviction of liars
        flagged, ghosts, votes = [], {}, {}
        Hc = H.copy()
        for _ in range(4):
            r = self._residuals(Hc, d_exp, gf, active)
            sc = self._vote(Hc, r, gf, thr, active)
            cand = [
                (v["frac"], v["strength"], k)
                for k, v in sc.items()
                if v["frac"] >= 0.5 and k not in flagged
            ]
            if not cand:
                break
            _, _, k = max(cand)
            flagged.append(k)
            ghosts[k] = dict(reported=float(H[k] - z[k]), ghost=sc[k]["ghost"] - float(z[k]))
            votes[k] = sc[k]["ballots"]
            Hc[k] = sc[k]["ghost"]
        r = self._residuals(Hc, d_exp, gf, active)

        # 2. Leak finder on the GHOST-CORRECTED picture
        leak_est = {
            i: float(-r[i]) for i in range(n) if i != SOURCE and active[i] and -r[i] > thr[i]
        }
        expected_in = float(sum(d_exp[i] for i in range(n) if active[i]))
        excess = tk["meter"] - expected_in
        total_est = sum(leak_est.values())
        confirmed = bool(leak_est) and excess > max(0.006, 0.5 * total_est)
        real_leaks = leak_est if confirmed else {}
        unverified = {} if confirmed else leak_est

        # 3. Water quality / contamination
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
                        comp.add(v)
                        stack.append(v)
            seen |= comp
            if len(comp) >= 2:
                plumes.append(sorted(comp))
            else:
                (i0,) = tuple(comp)
                strong = dcl[i0] > 0.08 and dtu[i0] > 0.25
                (plumes if (not out[i0] and strong) else q_faults).append(
                    sorted(comp) if not out[i0] and strong else i0
                )
        patient_zero = None
        if plumes:
            plume_nodes = sorted({i for p in plumes for i in p})
            patient_zero = self.patient_zero(
                exp_sol, ecl, plume_nodes, np.clip(dtu / 4.0, 0, None), active
            )

        # 4. Fingerprint sensor-level anomalies: cyberattack vs fault
        sensor_issues = {}
        for k in flagged + [q for q in q_faults if q not in flagged] + list(unverified):
            f = frames[k]
            forged = (not f["hmac_ok"]) or f["ttl"] != 64 or f["src_ip"] != net.ip[k]
            sensor_issues[k] = dict(
                kind="CYBERATTACK" if forged else "SENSOR_FAULT",
                vector=(
                    f"forged packet on topic aquila/n{k}/pressure from {f['src_ip']} "
                    f"(mac {f['mac']}, ttl {f['ttl']} vs 64, hmac {'OK' if f['hmac_ok'] else 'INVALID'})"
                )
                if forged
                else "valid signature, impossible physics -> hardware/calibration fault",
                ip=f["src_ip"] if forged else None
            )

        # 5. Bayesian Trust Score Update
        for i in range(n):
            if i in sensor_issues:
                self.trust[i] *= 0.5
            else:
                self.trust[i] = min(1.0, self.trust[i] + 0.02)

        # 6. Acoustic listener
        ac = self.listen(tk["wave"])
        if ac:
            self.crack_watch[ac["node"]] = dict(tick=tick, **ac)

        # 7. Incidents, smart valve doctor, quarantines
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
            open_inc(
                "MICRO_CRACK", k, dict(magnitude=round(w["mag"], 2), note="pre-leak: schedule repair")
            )

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
            if (
                inc["kind"] in ("CYBERATTACK", "SENSOR_FAULT")
                and key[1] not in sensor_issues
                and inc["status"] == "ACTIVE"
            ):
                inc["status"] = "MITIGATED (rogue source blocked / ghost sensor in use)"

        # 8. Flight recorder + classification
        digest = hashlib.sha1(
            json.dumps([round(float(x), 2) for x in P], default=json_sanitize).encode()
        ).hexdigest()[:16]
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
        self.summary = dict(
            tick=tick,
            classes=classes,
            flagged=flagged,
            ghosts=ghosts,
            votes=votes,
            leaks=real_leaks,
            unverified=unverified,
            plumes=plumes,
            patient_zero=patient_zero,
            sensor_issues=sensor_issues,
            acoustic=ac,
            excess_lps=excess * 1000,
            msgs=new_msgs,
            residual=r,
            thr=thr
        )
        return self.summary

    # ---------- Patient Zero Backtracking ----------
    def patient_zero(self, sol, ecl, plume_nodes, obs, active):
        """Reverse-time fluid DAG source search: finds injection origin node."""
        net = self.net
        out = net.flow_graph(sol["flows"])
        rev = {i: [] for i in range(net.n)}
        for u in range(net.n):
            for v, _, _ in out[u]:
                rev[v].append(u)
        cands, stack = set(plume_nodes), list(plume_nodes)
        while stack:
            v = stack.pop()
            for u in rev[v]:
                if u not in cands:
                    cands.add(u)
                    stack.append(u)
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
        worst = max(plume_nodes, key=lambda i: obs[i])
        path, cur = [worst], worst
        while cur != s and len(path) < 20:
            ups = [
                (sol["flows"][k] if net.edges[k][1] == cur else -sol["flows"][k], u)
                for u, k in net.nbrs[cur]
            ]
            ups = [(q, u) for q, u in ups if q > 0 and (u == s or u in cands)]
            if not ups:
                break
            cur = max(ups)[1]
            path.append(cur)
        return dict(
            node=int(s),
            rate=a,
            confidence=float(conf),
            age_min=float(age) / 60.0,
            path=path
        )

    # ---------- Smart Valve Doctor (Hospital Protection) ----------
    def valve_doctor(self, isolate_nodes):
        """Calculates boundary pipe isolation and proves hospitals maintain >=15m pressure floor."""
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
                steps = [
                    f"{label} valve V{net.edges[k][0]:02d}-{net.edges[k][1]:02d}"
                    for k in boundary
                ]
                return dict(
                    valves={k: factor for k in boundary},
                    steps=steps,
                    unserved=unserved,
                    hospitals=rows,
                    mode=label,
                    safe=True
                )
        return dict(
            valves={},
            steps=["No safe isolation: dispatch crew with bypass, notify hospital"],
            unserved=[],
            hospitals=[],
            mode="MANUAL",
            safe=False
        )

    # ---------- Acoustic Micro-Crack Listener ----------
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
        return dict(
            node=int(best),
            mag=mag,
            sensors=len(ids),
            t0=float(np.mean(t - self.net.dist[best, ids] / WAVE_SPEED))
        )

    def reopen_all(self):
        self.valves.clear()
        self.blocked_ips.clear()
        self.incidents.clear()
        self.crack_watch.clear()
        self.trust[:] = 1.0


class Simulation:
    """Master orchestrator combining World, LegacySCADA, Aquila, and Notifications."""

    def __init__(self, seed=1):
        self.world = PhysicalWorld(seed)
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

    def advance(self, n_ticks=1):
        for _ in range(n_ticks):
            tk = self.world.step()
            self.legacy.step(tk, self.world)
            summary = self.aquila.step(
                tk, self.world.expected_demand(), self.auto, self.legacy_delay_h
            )
            self.world.valves = dict(self.aquila.valves)
            self.world.blocked_ips = set(self.aquila.blocked_ips)
            alerts = self.notifier.dispatch(self.aquila.incidents, tk["tick"])
            self.new_alerts.extend(alerts)
            self.last_tick = tk
            self.history.append(dict(tick=tk["tick"], summary=summary, alerts=alerts))
            for m in summary.get("msgs", []):
                self.event_stream.append(dict(tick=tk["tick"], role="aquila", text=m))
        self.aquila.roi["ghost_avoided"] = self.legacy.ghost_dispatches
        return self.aquila.summary
