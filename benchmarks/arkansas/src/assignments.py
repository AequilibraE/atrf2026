import logging

import numpy as np
from aequilibrae import Project
from aequilibrae.routing import Network
from aequilibrae.traffic import TrafficAssignment, TrafficClass
from aequilibrae.traffic.vdf import bpr


# Segment, traffic class, AequilibraE mode, OMX matrix, PCE, value of time and toll.
CLASSES = (
    ("c", "car", "c", "AUTO", 1.0, 0.2, "hov1tollcost"),
    ("L", "light_truck", "c", "COMMTRK", 1.5, 0.5, "mttollcost"),
    ("T", "heavy_truck", "T", "HTRK", 2.5, 1.0, "httollcost"),
)
logger = logging.getLogger(__name__)


def load_demand(project: Project, period: str):
    demand = {}
    for segment, _, _, matrix, _, _, _ in CLASSES:
        collection = project.matrices.get_matrix(f"{period.upper()}.omx", subset=[matrix])
        collection[matrix] = collection[matrix].astype(np.float64, copy=False)
        demand[segment] = collection
    return demand


def assign_period(
    project: Project,
    network: Network,
    period: str,
    *,
    demand=None,
    algorithm="bfw",
    max_iterations=2000,
    rgap=1e-5,
    cores=None,
):
    logger.info("Assigning %s", period.upper())
    if demand is None:
        demand = load_demand(project, period)

    time_field = f"tt_{period}_10"
    classes = [
        TrafficClass(
            name=name,
            mode=mode,
            cost=time_field,
            demand=demand[segment],
            pce=pce,
            vot=vot,
            fixed_cost_field=toll,
        )
        for segment, name, mode, _, pce, vot, toll in CLASSES
    ]
    assignment = TrafficAssignment(
        network=network,
        classes=classes,
        time_field=time_field,
        capacity_field=f"{period}_assncap_10",
        vdf=bpr,
        name_mapping={"alpha": "alpha", "beta": "beta"},
        algorithm=algorithm,
        project=project,
    )
    assignment.execute(max_iterations=max_iterations, rgap=rgap, cores=cores)
    return assignment


def assignment(project: Project, network: Network, periods: list[str]):
    return {period: assign_period(project, network, period) for period in periods}
