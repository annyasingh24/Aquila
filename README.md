# 💧 Aquila: Physics-Aware AI Guardian for City Water Networks

> *"Hackers can spoof data, but they cannot hack the laws of physics."*

Aquila protects municipal water distribution networks by comparing digital IoT telemetry against real-time hydraulic physics (mass conservation $\sum Q_{in} = \sum Q_{out}$). It instantly distinguishes real broken pipes from lying, faulty, or hacked sensors—saving millions in wasted road excavation costs and preventing contaminated drinking water.

---

## 🏛️ Project Architecture (VS Code Directory Structure)

The codebase is organized into modular frontend and backend packages:

```
Aquila/
├── frontend/                     # Modern WebGL & Chart.js Interface
│   ├── index.html                # Single-page interface markup
│   ├── css/
│   │   └── style.css             # Design tokens, themes & layout styles
│   └── js/
│       ├── digital_twin.js       # Three.js 3D volumetric pipe mesh & particle flows
│       ├── simulator.js          # Attack simulator HUD & Byzantine consensus voting
│       ├── analytics.js          # Chart.js dynamic Before vs After graphs
│       └── app.js                # App lifecycle, toasts, theme & warzone loop
│
├── backend/                      # Python Fluid Simulation & Security Engine
│   ├── __init__.py               # Package exports
│   ├── config.py                 # Topology, fluid constants, noise & economics
│   ├── digital_twin.py           # EPANET-style linear hydraulic solver (Kirchhoff)
│   ├── simulation.py             # PhysicalWorld ground truth & rogue packet injector
│   ├── legacy_scada.py           # Benchmark legacy SCADA (blind threshold alarms)
│   ├── flight_recorder.py        # Cryptographic SHA-256 tamper-evident ledger
│   ├── notifier.py               # Push notification dispatcher (NTFY / phone alerts)
│   ├── engine.py                 # Aquila master defense (Swarm, Ghost Sensor, Valve Doctor, Patient Zero)
│   └── run_tests.py              # Modular test suite (23/23 verification scenarios)
│
├── aquila.py                     # Unified single-file engine & Streamlit dashboard launcher
├── index.html                    # Root SPA bundle served by Streamlit
└── README.md                     # System documentation & setup guide
```

---

## 🚀 Quickstart & Usage

### 1. Run the Live Web Dashboard
```bash
streamlit run aquila.py
```
* Access the interactive dashboard at **`http://localhost:8501`**.
* Features interactive 3D particle digital twin, attack simulator, Before vs After charts, sensor trust swarm, and God Mode warzone.

### 2. Run the 23-Scenario Verification Test Suite
Execute using either the modular backend or unified CLI:
```bash
# Modular Backend Test Suite:
python -m backend.run_tests

# Or Unified CLI:
python aquila.py --demo
```

---

## 🧠 Key Technologies & Physical Principles

1. **Hydraulic Digital Twin (`backend/digital_twin.py`)**:
   Runs a live mathematical model of fluid pressure heads and pipe flow rates using matrix conductance inversion.
2. **Federated Sensor Swarm & Edge BFT (`backend/engine.py`)**:
   Sensors perform peer-to-peer voting with physical neighbors without requiring central cloud processing.
3. **Ghost Sensor Technology (`backend/engine.py`)**:
   Recovers true physical pressure (~58.6 psi) mathematically from neighboring nodes when a sensor is spoofed.
4. **Smart Valve Doctor (`backend/engine.py`)**:
   Calculates pipe isolation plans while strictly verifying that City Hospital water pressure remains above safe thresholds ($\ge 15\text{m}$).
5. **Patient Zero DAG Backtracker (`backend/engine.py`)**:
   Walks backward along the fluid flow graph to identify the exact origin junction and injection timestamp of chemical contamination.
6. **Cryptographic Flight Recorder (`backend/flight_recorder.py`)**:
   SHA-256 hash-chained immutable audit log.
