"""
Water Network Topologies for Aquila Digital Twin.
Defines benchmark District Metered Areas (DMAs) with hydraulic properties:
junctions, elevations, base demands, pipes, lengths, diameters, roughness coefficients.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Node:
    id: str
    type: str  # 'junction', 'reservoir', 'tank'
    elevation: float  # meters
    base_demand: float  # Liters per second (L/s)
    x: float  # coordinate for visualization
    y: float
    chlorine: float = 1.2  # mg/L baseline
    turbidity: float = 0.5  # NTU baseline
    ph: float = 7.4  # pH baseline


@dataclass
class Pipe:
    id: str
    from_node: str
    to_node: str
    length: float  # meters
    diameter: float  # millimeters
    roughness: float = 130.0  # Hazen-Williams C-factor
    flow: float = 0.0  # L/s
    velocity: float = 0.0  # m/s
    status: str = "OPEN"


@dataclass
class WaterNetwork:
    name: str
    description: str
    nodes: Dict[str, Node]
    pipes: Dict[str, Pipe]
    reservoir_head: float = 55.0  # meters of head at primary supply


def get_metropolitan_dma_network() -> WaterNetwork:
    """
    Returns an interconnected 12-node municipal District Metered Area (DMA).
    Realistic urban topology with primary reservoir, pump station node,
    distribution loops, commercial, residential, and industrial demand zones.
    """
    nodes = {
        "R1": Node("R1", "reservoir", elevation=15.0, base_demand=0.0, x=50, y=300),
        "J1": Node("J1", "junction", elevation=18.0, base_demand=8.5, x=150, y=300),
        "J2": Node("J2", "junction", elevation=22.0, base_demand=12.0, x=280, y=380),
        "J3": Node("J3", "junction", elevation=20.0, base_demand=15.5, x=280, y=220),
        "J4": Node("J4", "junction", elevation=25.0, base_demand=22.0, x=420, y=420),
        "J5": Node("J5", "junction", elevation=21.0, base_demand=18.0, x=420, y=300),
        "J6": Node("J6", "junction", elevation=19.0, base_demand=14.0, x=420, y=180),
        "J7": Node("J7", "junction", elevation=27.0, base_demand=25.0, x=580, y=380),
        "J8": Node("J8", "junction", elevation=24.0, base_demand=20.0, x=580, y=220),
        "J9": Node("J9", "junction", elevation=28.0, base_demand=16.0, x=720, y=350),
        "J10": Node("J10", "junction", elevation=26.0, base_demand=14.5, x=720, y=250),
        "T1": Node("T1", "tank", elevation=32.0, base_demand=-15.0, x=840, y=300),
    }

    pipes = {
        "P1": Pipe("P1", "R1", "J1", length=600, diameter=400, roughness=135),
        "P2": Pipe("P2", "J1", "J2", length=450, diameter=300, roughness=130),
        "P3": Pipe("P3", "J1", "J3", length=480, diameter=300, roughness=130),
        "P4": Pipe("P4", "J2", "J4", length=500, diameter=250, roughness=125),
        "P5": Pipe("P5", "J2", "J5", length=420, diameter=200, roughness=125),
        "P6": Pipe("P6", "J3", "J5", length=420, diameter=200, roughness=125),
        "P7": Pipe("P7", "J3", "J6", length=490, diameter=250, roughness=125),
        "P8": Pipe("P8", "J4", "J7", length=520, diameter=200, roughness=120),
        "P9": Pipe("P9", "J5", "J7", length=440, diameter=200, roughness=120),
        "P10": Pipe("P10", "J5", "J8", length=440, diameter=200, roughness=120),
        "P11": Pipe("P11", "J6", "J8", length=510, diameter=200, roughness=120),
        "P12": Pipe("P12", "J7", "J9", length=460, diameter=200, roughness=120),
        "P13": Pipe("P13", "J8", "J10", length=470, diameter=200, roughness=120),
        "P14": Pipe("P14", "J9", "J10", length=350, diameter=150, roughness=115),
        "P15": Pipe("P15", "J9", "T1", length=580, diameter=250, roughness=125),
        "P16": Pipe("P16", "J10", "T1", length=590, diameter=250, roughness=125),
    }

    return WaterNetwork(
        name="Indraprastha DMA-4",
        description="Municipal 12-Node Urban District Metered Area with dual looping and elevated storage balancing",
        nodes=nodes,
        pipes=pipes,
        reservoir_head=60.0,
    )
