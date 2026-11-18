"""Build and compare bicycle routes for the Mount Isa workshop."""

import numpy as np
import pandas as pd
from aequilibrae import Project
from aequilibrae.route_choice import RouteChoice
from aequilibrae.routing import Graph, Network

BICYCLE_MODE = "b"
COST_FIELD = "distance"


def build_bicycle_graph(network: Network) -> Graph:
    """Use link distance in metres as the routing cost."""
    return network.build_graph(
        mode=BICYCLE_MODE,
        cost=COST_FIELD,
        compact=True,
        remove_dead_ends=True,
        block_centroid_flows=False,
    )


def run_choice_set(
    graph: Graph, od_pair: tuple[int, int], algorithm: str
) -> pd.DataFrame:
    """Generate alternatives and calculate their path-size logit probabilities."""
    choice = RouteChoice(graph)
    choice.set_choice_set_generation(
        algorithm=algorithm,
        max_routes=10,
        max_depth=12,
        disutility_cutoff_coefficient=1.05,
        disutility_cutoff_constant=0,
    )
    choice.prepare([od_pair])
    choice.execute(perform_assignment=True)
    return choice.get_results()


def shortest_distance(graph: Graph, od_pair: tuple[int, int]) -> float | None:
    """Return the shortest distance in metres, or None if there is no route."""
    path = graph.compute_path(*od_pair, early_exit=True)
    return float(path.milepost[-1]) if path.milepost is not None else None


class BicycleRouteChoice:
    """Run the comparison and link closure exercises on a prepared project."""

    algorithms = ("BFSLE", "LP")

    def __init__(self, project: Project):
        self.network = project.road.build_network(
            fields=[COST_FIELD], modes=[BICYCLE_MODE]
        )
        self.graph = build_bicycle_graph(self.network)
        self._closure_graph = None
        self._closed_link = None

        links = self.network.links
        centroids = self.network.centroids
        touches_centroid = links["a_node"].isin(centroids) | links["b_node"].isin(
            centroids
        )
        is_bicycle_link = self.network.mode_mask(BICYCLE_MODE)
        self.road_ids = frozenset(
            links.loc[is_bicycle_link & ~touches_centroid, "link_id"]
        )

    def compare(self, od_pair: tuple[int, int]) -> dict[str, pd.DataFrame]:
        """Return one route table for each method."""
        return {
            method: run_choice_set(self.graph, od_pair, method)
            for method in self.algorithms
        }

    def baseline_distance(self, od_pair: tuple[int, int]) -> float | None:
        """Return the shortest distance before any road is closed."""
        return shortest_distance(self.graph, od_pair)

    def close_link(
        self, od_pair: tuple[int, int], link_id: int, algorithm: str
    ) -> tuple[float | None, pd.DataFrame]:
        """Return the shortest distance and route table with one road closed."""
        if link_id not in self.road_ids:
            raise ValueError(f"Link {link_id} is not an imported bicycle road.")

        # Reuse a separate graph for closures to preserve the original costs.
        if self._closure_graph is None:
            self._closure_graph = build_bicycle_graph(self.network)
        if link_id != self._closed_link:
            costs = self.network.field_values(COST_FIELD).copy()
            # Each direction has its own cost entry with the same physical link ID.
            costs[self.network.link_ids == link_id] = np.inf
            self._closure_graph.set_costs(costs)
            self._closed_link = link_id

        distance = shortest_distance(self._closure_graph, od_pair)
        routes = run_choice_set(self._closure_graph, od_pair, algorithm)
        return distance, routes
