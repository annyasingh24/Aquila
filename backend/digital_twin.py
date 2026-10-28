"""
AQUILA Digital Twin (Linear Hydraulic & Water Quality Solver)
=============================================================
Implements mass conservation Kirchhoff equations: sum(Q_in) - sum(Q_out) = 0.
Solves pressure head matrix via linear matrix conductance inversion.
Simulates orifice law leaks and advective contaminant transport.
"""

import math
import heapq
import numpy as np

from backend.config import (
    GRID, SPACING, SOURCE, H_SOURCE, CL_DOSE, CL_DECAY, CL_ALPHA,
    PIPE_AREA
)


class HydraulicTwin:
    """Pipe network + linear hydraulic / water-quality solver."""

    def __init__(self, grid=GRID, seed=7):
        rng = np.random.default_rng(seed)
        self.grid, self.n = grid, grid * grid
        n = self.n
        self.xy = np.array([[(i % grid) * SPACING, (i // grid) * SPACING] for i in range(n)])
        # Multi-tiered city terrain (reservoir -> downtown -> hospital hill -> lowlands)
        self.z = 4 + 3 * np.sin(self.xy[:, 0] / 170) + 3 * np.cos(self.xy[:, 1] / 140)
        self.edges = []
        for i in range(n):
            r, c = divmod(i, grid)
            if c < grid - 1:
                self.edges.append((i, i + 1))
            if r < grid - 1:
                self.edges.append((i, i + grid))
        self.m = len(self.edges)
        self.g0 = 0.03 * rng.uniform(0.85, 1.15, self.m)  # conductance m3/s per m head
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
        """Calculates effective conductance accounting for throttled or closed valves."""
        return self.g0 * np.array([valves.get(k, 1.0) for k in range(self.m)])

    def reachable(self, gf):
        """BFS reachability check from source reservoir."""
        seen, stack = {SOURCE}, [SOURCE]
        while stack:
            i = stack.pop()
            for j, k in self.nbrs[i]:
                if gf[k] > 1e-12 and j not in seen:
                    seen.add(j)
                    stack.append(j)
        return np.array([i in seen for i in range(self.n)])

    def _head(self, gf, d, reach):
        """Solves matrix Laplacian for steady-state head at all connected junctions."""
        n = self.n
        L = np.zeros((n, n))
        for k, (a, b) in enumerate(self.edges):
            g = gf[k]
            L[a, a] += g
            L[b, b] += g
            L[a, b] -= g
            L[b, a] -= g
        free = [i for i in range(n) if reach[i] and i != SOURCE]
        h = np.where(reach, H_SOURCE, self.z).astype(float)
        if free:
            rhs = -d[free] - L[free, SOURCE] * H_SOURCE
            h[free] = np.linalg.solve(L[np.ix_(free, free)], rhs)
        return h

    def solve(self, demand, valves=None, leaks=None):
        """Solves network heads and edge flow rates using orifice law iteration."""
        valves, leaks = valves or {}, leaks or {}
        gf = self.eff_g(valves)
        reach = self.reachable(gf)
        lq = {k: 0.0 for k in leaks}
        for _ in range(10):
            d = demand.copy()
            for k, q in lq.items():
                d[k] += q
            h = self._head(gf, d, reach)
            lq = {
                k: (leaks[k] * math.sqrt(max(h[k] - self.z[k], 0) / 40.0) if reach[k] else 0.0)
                for k in leaks
            }
        d = demand.copy()
        for k, q in lq.items():
            d[k] += q
        h = self._head(gf, d, reach)
        flows = np.array([
            gf[k] * (h[a] - h[b]) if (reach[a] and reach[b]) else 0.0
            for k, (a, b) in enumerate(self.edges)
        ])
        inflow = float(sum(d[i] for i in range(self.n) if reach[i]))
        return dict(h=h, flows=flows, reach=reach, inflow=inflow, leakq=lq, gf=gf)

    def flow_graph(self, flows):
        """Constructs directed graph: node -> list of (downstream_node, q, edge)."""
        out = [[] for _ in range(self.n)]
        for k, (a, b) in enumerate(self.edges):
            q = flows[k]
            if q > 1e-9:
                out[a].append((b, q, k))
            elif q < -1e-9:
                out[b].append((a, -q, k))
        return out

    def quality(self, sol, contam=None):
        """Steady-state chlorine and contaminant mixing along the fluid DAG."""
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
            mix = sum(
                q * cl[j] * math.exp(-CL_DECAY * PIPE_AREA * self.length[k] / q)
                for j, q, k in inflow[i]
            ) / tot
            inj = contam.get(i, 0.0)
            cl[i] = mix * math.exp(-CL_ALPHA * inj / tot)
            con[i] = (sum(q * con[j] for j, q, _ in inflow[i]) + inj) / tot
        tu = np.where(reach, 0.25 + 4.0 * con, 0.0)
        return cl, tu, con

    def travel_times(self, flows, src):
        """Dijkstra calculation of fluid travel time (seconds) from src along flow direction."""
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
    """Calculates diurnal city demand cycle (morning showers peak, nighttime lull)."""
    return 1 + 0.3 * math.sin(2 * math.pi * (t_min - 360) / 1440)
