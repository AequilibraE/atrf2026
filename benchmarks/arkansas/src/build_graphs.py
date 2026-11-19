import numpy as np

from aequilibrae import Project
from aequilibrae.routing import Network


PERIODS = ("am", "md", "pm", "nt")
TOLL_FIELDS = ("hov1tollcost", "mttollcost", "httollcost")


def build_network(project: Project, periods=PERIODS) -> Network:
    fields = [
        "distance", "builtyear", "removedyear", "mode_code", "exclusionset", "alpha", "beta", *TOLL_FIELDS
    ]
    for period in periods:
        fields.extend((f"tt_{period}_10", f"{period}_assncap_10"))
    source = project.road.build_network(fields=fields, modes=["c", "T"])

    # These three nodes are outside the OMX zone index.
    centroids = source.centroids[~np.isin(source.centroids, [4701, 4702, 4703])]
    links = source.links
    connectors = links["a_node"].isin(centroids) | links["b_node"].isin(centroids)
    outside_model_year = (
        links["builtyear"].gt(2010)
        | links["removedyear"].lt(2010)
        | (links["builtyear"].isna() & links["removedyear"].isna())
    )
    outside_road_modes = links["mode_code"].lt(10) | links["mode_code"].gt(11)
    road_links = ~(outside_model_year | outside_road_modes)
    links = links.loc[(connectors | road_links) & links["a_node"].ne(links["b_node"])].copy()

    exclusions = links["exclusionset"]
    passenger = links["modes"].str.contains("c", regex=False) & ~exclusions.isin(("TruckOnly", "HOV2", "HOV3"))
    truck = links["modes"].str.contains("T", regex=False) & ~exclusions.isin(("PassengerOnly", "HOV2", "HOV3"))
    links["modes"] = passenger.map({True: "c", False: ""}) + truck.map({True: "T", False: ""})

    defaults = {field: 0.0 for field in TOLL_FIELDS}
    for direction in ("ab", "ba"):
        defaults[f"alpha_{direction}"] = 0.15
        defaults[f"beta_{direction}"] = 4.0
        for period in periods:
            defaults[f"tt_{period}_10_{direction}"] = 0.001
            defaults[f"{period}_assncap_10_{direction}"] = 1.0

    return Network(
        links.fillna(defaults),
        modes=source.modes,
        centroids=centroids,
        allow_uturns=source.allow_uturns,
        lonlat=source.lonlat,
    )
