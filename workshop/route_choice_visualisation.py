"""Show the Mount Isa route choice exercises with Lonboard and Jupyter widgets."""

from base64 import b64encode
from dataclasses import dataclass
from math import log2
from pathlib import Path

import geopandas as gpd
import ipywidgets as widgets
import numpy as np
import pandas as pd
from lonboard import ColumnLayer, Map, PathLayer, PolygonLayer, ScatterplotLayer
from matplotlib import colormaps
from shapely.geometry import Point

MAP_HEIGHT = 900
ROUTE_WIDTH = 6
ROUTE_COLOUR_MAP = "inferno"
ROUTE_COLOUR_MAP_r = ROUTE_COLOUR_MAP + "_r"
WORLD_METRES_PER_PIXEL = 40_075_017 / 512
SHARED_COLOUR, BFSLE_COLOUR, LP_COLOUR = colormaps[ROUTE_COLOUR_MAP_r](
    [0.15, 0.45, 0.75], bytes=True
)[:, :3].tolist()
METHOD_COLOURS = {"BFSLE": BFSLE_COLOUR, "LP": LP_COLOUR}
ZONE_LABELS = {"zone_id": "Zone ID", "sa1_code_2021": "SA1 code"}


def _map_styles():
    # Deck.gl positions its tooltip relative to this container.
    css = (
        str(Map._css)
        + """
    .workshop-map .deck-widgets-root {
        position: absolute;
        inset: 0;
        pointer-events: none;
    }
    """
    )
    brand_file = Path(__file__).with_name("data") / "brand-mark.svg"
    if not brand_file.is_file():
        return css
    brand_mark = b64encode(brand_file.read_bytes()).decode("ascii")
    return (
        css
        + f"""
    .workshop-map .deck-widgets-root::after {{
        content: "";
        position: absolute;
        top: 12px;
        right: 52px;
        width: 48px;
        height: 40px;
        background-color: currentColor;
        mask: url("data:image/svg+xml;base64,{brand_mark}") center / contain no-repeat;
        opacity: 0.28;
        pointer-events: none;
    }}
    """
    )


class WorkshopMap(Map):
    """Use the workshop's tooltip and brand styling."""

    _css = _map_styles()

    def __init__(self, layers, **kwargs):
        super().__init__(layers, **kwargs)
        self.add_class("workshop-map")


def make_zone_layer(zone_data):
    """Draw the workshop's zone boundaries and highlight zones on hover."""
    return PolygonLayer.from_geopandas(
        zone_data,
        get_fill_color=[57, 125, 137, 25],
        get_line_color=[67, 117, 129, 210],
        stroked=True,
        line_width_units="pixels",
        get_line_width=1.3,
        auto_highlight=True,
        highlight_color=[57, 125, 137, 55],
    )


def map_view(projected_geometry, width=460, *, height=MAP_HEIGHT):
    """Fit Web Mercator geometry in the available map space."""
    west, south, east, north = projected_geometry.total_bounds
    centre = Point((west + east) / 2, (south + north) / 2)
    centre = gpd.GeoSeries([centre], crs=3857).to_crs(4326).iloc[0]
    metres_per_pixel = max((east - west) / width, (north - south) / (height - 100), 5)
    return {
        "longitude": centre.x,
        "latitude": centre.y,
        "zoom": log2(WORLD_METRES_PER_PIXEL / metres_per_pixel),
    }


def _road_layer(links):
    road_data = (
        links[["link_type", "geometry"]]
        .reset_index()
        .rename(columns={"link_id": "Link ID", "link_type": "Link type"})
    )
    return PathLayer.from_geopandas(
        road_data,
        width_units="pixels",
        get_width=1.1,
        get_color=[121, 131, 145, 135],
        auto_highlight=True,
    )


def _zone_centroids(nodes):
    return nodes.loc[nodes["is_centroid"].eq(1), ["node_id", "geometry"]].rename(
        columns={"node_id": "Zone ID"}
    )


def _centroid_layer(centroids, *, visible=True, pickable=True):
    return ScatterplotLayer.from_geopandas(
        centroids,
        radius_units="pixels",
        get_radius=2.5,
        get_fill_color=[67, 117, 129],
        visible=visible,
        pickable=pickable,
    )


def _network_map(layers, view_state):
    return WorkshopMap(
        layers=layers,
        view_state=view_state,
        basemap=None,
        # height=MAP_HEIGHT,
        show_side_panel=False,
        show_tooltip=True,
        custom_attribution="© OpenStreetMap contributors",
    )


def _zone_controls(map_widget, zone_view, set_zones_visible):
    show_zones = widgets.Checkbox(
        description="SA1 zones", value=True, indent=False, layout={"width": "auto"}
    )
    fit_zones = widgets.Button(description="Fit zones", layout={"width": "100px"})

    def fit_view(_):
        show_zones.value = True
        map_widget.set_view_state(**zone_view)

    show_zones.observe(lambda change: set_zones_visible(change["new"]), names="value")
    fit_zones.on_click(fit_view)
    return show_zones, fit_zones


def network_overview(links, nodes, zones, column_names):
    """Show roads and Census totals as bars at the zone centroids."""
    labour_labels = {
        "total": "Census total",
        **{
            column: label
            for label, column in column_names.items()
            if column not in {"sa1_code_2021", "total"}
        },
    }
    labels = {**ZONE_LABELS, **labour_labels}
    zone_data = zones.reset_index()[[*labels, "geometry"]].rename(columns=labels)
    fields = list(labour_labels.values())
    zone_data[fields] = (
        zone_data[fields].astype("Int64").astype("string").fillna("No data")
    )

    zone_layer = make_zone_layer(zone_data)
    road_layer = _road_layer(links.set_index("link_id"))
    population_layers = []
    bars = _zone_centroids(nodes).merge(
        zone_data.drop(columns="geometry"), on="Zone ID"
    )
    totals = bars["Zone ID"].map(zones.set_index("zone_id")["total"])
    has_population = totals.gt(0).fillna(False)
    if has_population.any():
        population_layers.append(
            ColumnLayer.from_geopandas(
                bars.loc[has_population].reset_index(drop=True),
                get_elevation=totals.loc[has_population].to_numpy(dtype=np.float32),
                elevation_scale=3,
                radius=70,
                radius_units="meters",
                disk_resolution=4,
                angle=45,
                flat_shading=True,
                extruded=True,
                get_fill_color=[30, 116, 135, 225],
                auto_highlight=True,
            )
        )
    zone_view = {
        **map_view(zone_data.geometry.to_crs(3857)),
        "pitch": 50,
        "bearing": -15,
    }
    map_widget = _network_map([zone_layer, road_layer, *population_layers], zone_view)

    def set_zones_visible(visible):
        zone_layer.visible = visible
        for layer in population_layers:
            layer.visible = visible

    controls = widgets.HBox(
        _zone_controls(map_widget, zone_view, set_zones_visible),
        layout={"flex_flow": "row wrap", "align_items": "center"},
    )
    return widgets.VBox([controls, map_widget])


def _included_link_ids(routes):
    return {
        int(link_id)
        for path in routes.loc[routes["mask"], "route set"]
        for link_id in path
    }


def _link_layer(links, link_ids, label, colour, *, width=4, visible=True):
    data = links.loc[sorted(link_ids), ["geometry"]].reset_index()
    data = data.rename(columns={"link_id": "Link ID"}).assign(Status=label)
    return PathLayer.from_geopandas(
        data,
        width_units="pixels",
        get_width=width,
        get_color=list(colour),
        auto_highlight=True,
        visible=visible,
    )


def _swatch(colour):
    rgb = ",".join(map(str, colour))
    return f'<span style="color:rgb({rgb})" aria-hidden="true">●</span>'


def _route_colour_bar():
    colours = colormaps[ROUTE_COLOUR_MAP_r](np.linspace(0, 1, 32), bytes=True)
    stops = ", ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b, _ in colours)
    return widgets.HTML(
        '<div style="width:100%;max-width:320px">'
        "<div>Route cost rank</div>"
        f'<div aria-hidden="true" style="height:12px;'
        f'background:linear-gradient(to left,{stops})"></div>'
        '<div style="display:flex;justify-content:space-between">'
        "<span>Highest cost</span><span>Lowest cost</span></div></div>"
    )


@dataclass
class _MapRoute:
    layer: PathLayer
    label: str
    summary: str
    included: bool


def _make_route_layers(routes, links):
    columns = ["route set", "cost", "probability", "mask"]
    ordered = routes.sort_values("cost", kind="stable")[columns]
    positions = [0.5] if len(ordered) == 1 else np.linspace(0, 1, len(ordered))
    colours = colormaps[ROUTE_COLOUR_MAP_r](positions, bytes=True)[:, :3].tolist()
    layers = {}
    for number, (link_ids, cost, probability, included) in enumerate(
        ordered.itertuples(index=False, name=None), start=1
    ):
        label = f"Route {number}" if included else f"Route {number} (excluded)"
        details = {"Route": label, "Distance": f"{cost / 1000:.2f} km"}
        if included and pd.notna(probability):
            details["Probability"] = f"{100 * probability:.3g}%"
        colour = colours[number - 1]
        data = links.loc[link_ids, ["geometry"]].assign(**details)
        layer = PathLayer.from_geopandas(
            data,
            width_units="pixels",
            get_width=ROUTE_WIDTH,
            cap_rounded=True,
            get_color=[*colour, 215],
            auto_highlight=True,
            visible=included,
        )
        summary = f"{_swatch(colour)} " + " · ".join(details.values())
        layers[number] = _MapRoute(layer, label, summary, included)
    return layers


class _RouteMap:
    """Keep the map and its controls in place as routes change."""

    def __init__(self, links, zone_data, centroids, zone_view):
        self.links = links
        self.centroids = centroids
        self.routes = {}
        self.overlays = ()
        self.markers = ()
        self.comparing = False
        self.zone_layer = make_zone_layer(zone_data)
        self.road_layer = _road_layer(links)
        self.map = _network_map([self.zone_layer, self.road_layer], zone_view)

        self.summary = widgets.HTML()
        self.route_picker = widgets.Dropdown(
            description="Route",
            layout=widgets.Layout(width="min(285px, 100%)"),
            style={"description_width": "auto"},
        )
        self.show_zones, fit_zones = _zone_controls(
            self.map, zone_view, self._set_zones_visible
        )
        show_roads = widgets.Checkbox(
            description="Roads", value=True, indent=False, layout={"width": "auto"}
        )
        self.route_picker.observe(self._update_route, names="value")
        show_roads.observe(
            lambda change: setattr(self.road_layer, "visible", change["new"]),
            names="value",
        )
        controls = widgets.HBox(
            [self.route_picker, self.show_zones, show_roads, fit_zones],
            layout={"flex_flow": "row wrap", "align_items": "center"},
        )
        self.widget = widgets.VBox([self.summary, controls, self.map])

    def set_trip(self, od_pair, routes, view, overlays=()):
        self.od_pair = od_pair
        old_markers = self.markers
        self.markers = self._make_markers(od_pair)
        self.set_routes(routes, overlays)
        for layer in old_markers:
            layer.close()
        self.map.set_view_state(**view)

    def set_routes(self, routes, overlays=()):
        old_layers = [route.layer for route in self.routes.values()]
        old_layers.extend(self.overlays)
        self.routes = _make_route_layers(routes, self.links)
        self.overlays = overlays
        # Draw higher-cost routes first so the shortest route is on top.
        self.map.layers = [
            self.zone_layer,
            self.road_layer,
            *(route.layer for route in reversed(self.routes.values())),
            *self.overlays,
            *self.markers,
        ]
        self.route_picker.options = [
            ("All included routes", None),
            *((route.label, number) for number, route in self.routes.items()),
        ]
        self.route_picker.value = None
        self._update_route()
        for layer in old_layers:
            layer.close()

    def show_comparison(self, enabled):
        self.comparing = enabled
        for layer in self.overlays:
            layer.visible = enabled
        self._update_route()

    def _make_markers(self, od_pair):
        labels = dict(zip(od_pair, ("Origin", "Destination")))
        endpoint_mask = self.centroids["Zone ID"].isin(labels)
        endpoints = self.centroids.loc[endpoint_mask].copy()
        endpoints["Location"] = endpoints["Zone ID"].map(labels)
        other_centroids = _centroid_layer(
            self.centroids.loc[~endpoint_mask],
            visible=self.show_zones.value,
        )
        endpoint_layer = ScatterplotLayer.from_geopandas(
            endpoints,
            radius_units="pixels",
            get_radius=7,
            get_fill_color=np.array(
                [
                    [24, 117, 75] if label == "Origin" else [124, 48, 121]
                    for label in endpoints["Location"]
                ],
                dtype=np.uint8,
            ),
            stroked=True,
            line_width_units="pixels",
            get_line_width=2,
            get_line_color=[255, 255, 255],
        )
        return other_centroids, endpoint_layer

    def _update_route(self, _=None):
        selected = self.route_picker.value
        self.route_picker.disabled = self.comparing or not self.routes
        for number, route in self.routes.items():
            visible = route.included if selected is None else number == selected
            route.layer.visible = visible and not self.comparing
            route.layer.get_width = (
                ROUTE_WIDTH if selected is None else ROUTE_WIDTH + 1.5
            )
        if selected is not None and not self.comparing:
            detail = self.routes[selected].summary
        elif self.routes:
            included = sum(route.included for route in self.routes.values())
            detail = f"{included} of {len(self.routes)} routes included"
        else:
            detail = "No routes found"
        origin, destination = self.od_pair
        self.summary.value = f"<b>Zone {origin} → Zone {destination}</b> · {detail}"

    def _set_zones_visible(self, visible):
        self.zone_layer.visible = visible
        if self.markers:
            self.markers[0].visible = visible


def _closure_status(baseline, distance, closed_link):
    if baseline is None:
        return "No bicycle route connects these zones on the original network."
    if closed_link is None:
        return f"<b>Original shortest route</b> · {baseline / 1000:.2f} km"
    if distance is None:
        return f"<b>Link {closed_link} closed</b> · No route connects these zones."
    change = round(distance - baseline)
    return (
        f"<b>Link {closed_link} closed</b> · "
        f"Shortest route {baseline / 1000:.2f} → {distance / 1000:.2f} km "
        f"({change:+,d} m)"
    )


class _LinkClosure:
    def __init__(self, routing, route_map, projected_roads):
        self.routing = routing
        self.route_map = route_map
        self.roads = projected_roads
        self.road_index = self.roads.sindex
        self.active_link = None
        self.method = widgets.Dropdown(
            options=routing.algorithms, value="LP", description="Method"
        )
        self.link_id = widgets.Text(
            description="Link ID", placeholder="Click a road or enter an ID"
        )
        apply = widgets.Button(description="Close link", button_style="primary")
        self.reopen = widgets.Button(description="Reopen link", disabled=True)
        self.status = widgets.HTML()
        self.message = widgets.HTML()
        self.route_map.map.on_click(self._pick_road)
        apply.on_click(self._close_link)
        self.reopen.on_click(lambda _: self._show_scenario())
        self.method.observe(
            lambda _: self._show_scenario(self.active_link), names="value"
        )

        controls = widgets.HBox(
            [self.method, self.link_id, apply, self.reopen],
            layout={"flex_flow": "row wrap"},
        )
        self.widget = widgets.VBox(
            [controls, self.status, self.message, self.route_map.widget]
        )

    def set_trip(self, od_pair, results, view):
        self.od_pair = od_pair
        self.results = results
        self.baseline = self.routing.baseline_distance(od_pair)
        self.route_map.set_trip(od_pair, results[self.method.value], view)
        self._set_status(self.baseline, closed_link=None)
        self.link_id.value = ""

    def _pick_road(self, coordinates):
        zoom = self.route_map.map.view_state.zoom
        metres_per_pixel = WORLD_METRES_PER_PIXEL / 2**zoom
        point = gpd.GeoSeries([Point(*coordinates)], crs=4326).to_crs(3857).iloc[0]
        hits = self.road_index.nearest(
            point, return_all=False, max_distance=8 * metres_per_pixel
        )
        if hits.size:
            self.link_id.value = str(self.roads.index[hits[1, 0]])
            self.message.value = "Link selected. Click <b>Close link</b> to test it."
        else:
            self.message.value = "No bicycle road is close to that point."

    def _close_link(self, _):
        try:
            selected = int(self.link_id.value)
        except ValueError:
            self.message.value = "Click a bicycle road or enter its link ID."
            return
        if selected not in self.roads.index:
            self.message.value = "Choose an imported bicycle link from the map."
            return
        self._show_scenario(selected)

    def _show_scenario(self, closed_link=None):
        method = self.method.value
        if closed_link is None:
            distance, routes = self.baseline, self.results[method]
            overlays = ()
        else:
            distance, routes = self.routing.close_link(
                self.od_pair, closed_link, method
            )
            overlays = (
                _link_layer(
                    self.route_map.links,
                    {closed_link},
                    "Closed in both directions",
                    [185, 38, 52],
                    width=6,
                ),
            )
        self.route_map.set_routes(routes, overlays)
        self._set_status(distance, closed_link)

    def _set_status(self, distance, closed_link):
        self.active_link = closed_link
        self.reopen.disabled = closed_link is None
        self.status.value = _closure_status(self.baseline, distance, closed_link)
        self.message.value = ""


def route_choice_workshop(routing, links, nodes, zones):
    """Show the method comparison and road closure tabs for a bicycle model."""
    zone_ids = sorted(int(zone) for zone in zones["zone_id"].unique())
    if len(zone_ids) < 2:
        raise ValueError("The workshop needs at least two zones.")
    origin_id = 14 if 14 in zone_ids else zone_ids[0]
    destination_id = (
        37
        if 37 in zone_ids and origin_id != 37
        else next(zone for zone in zone_ids if zone != origin_id)
    )
    origin = widgets.Dropdown(options=zone_ids, value=origin_id, description="Origin")
    destination = widgets.Dropdown(
        options=zone_ids, value=destination_id, description="Destination"
    )
    run = widgets.Button(description="Run comparison", button_style="primary")
    status = widgets.HTML()

    links = links.set_index("link_id")
    zone_data = zones.reset_index()[[*ZONE_LABELS, "geometry"]].rename(
        columns=ZONE_LABELS
    )
    centroids = _zone_centroids(nodes)
    zone_view = map_view(zone_data.geometry.to_crs(3857))
    projected_links = links.geometry.to_crs(3857)
    projected_centroids = centroids.set_index("Zone ID").geometry.to_crs(3857)

    maps = {
        method: _RouteMap(links, zone_data, centroids, zone_view)
        for method in routing.algorithms
    }
    bfs_map, lp_map = maps.values()
    # Keep pan, zoom and Fit zones in step across both comparison maps.
    widgets.link((bfs_map.map, "view_state"), (lp_map.map, "view_state"))
    closure = _LinkClosure(
        routing,
        _RouteMap(links, zone_data, centroids, zone_view),
        projected_links.loc[projected_links.index.isin(routing.road_ids)],
    )
    compare_links = widgets.Checkbox(
        description="Compare link use", indent=False, layout={"width": "auto"}
    )
    legend = widgets.HTML(layout={"display": "none"})
    route_colour_bar = _route_colour_bar()

    def toggle_comparison(change):
        enabled = change["new"]
        legend.layout.display = "" if enabled else "none"
        route_colour_bar.layout.display = "none" if enabled else ""
        for panel in maps.values():
            panel.show_comparison(enabled)

    compare_links.observe(toggle_comparison, names="value")
    panels = [
        widgets.VBox(
            [widgets.HTML(f"<b>{method}</b>"), panel.widget],
            layout={"flex": "1 1 360px", "min_width": "0"},
        )
        for method, panel in maps.items()
    ]
    row = widgets.HBox(
        panels, layout={"flex_flow": "row wrap", "align_items": "flex-start"}
    )
    comparison = widgets.VBox([compare_links, legend, route_colour_bar, row])
    tabs = widgets.Tab(
        children=[comparison, widgets.VBox([_route_colour_bar(), closure.widget])],
        titles=["BFSLE vs LP", "Close a link"],
    )

    def update_trip(_):
        od_pair = origin.value, destination.value
        if od_pair[0] == od_pair[1]:
            status.value = "Choose two different zones."
            return
        run.disabled = True
        try:
            results = routing.compare(od_pair)
            bfs_links = _included_link_ids(results["BFSLE"])
            lp_links = _included_link_ids(results["LP"])
            shared = bfs_links & lp_links
            unique = {"BFSLE": bfs_links - lp_links, "LP": lp_links - bfs_links}
            legend.value = " &nbsp; ".join(
                [
                    f"{_swatch(SHARED_COLOUR)} Both methods ({len(shared)})",
                    *(
                        f"{_swatch(METHOD_COLOURS[method])} {method} only ({len(ids)})"
                        for method, ids in unique.items()
                    ),
                ]
            )
            trip_geometry = pd.concat(
                [
                    projected_links.loc[sorted(bfs_links | lp_links)],
                    projected_centroids.reindex(od_pair).dropna(),
                ]
            )
            comparison_view = (
                map_view(trip_geometry, width=320)
                if not trip_geometry.empty
                else zone_view
            )
            for method, panel in maps.items():
                overlays = [
                    _link_layer(links, ids, label, colour, visible=compare_links.value)
                    for ids, label, colour in (
                        (shared, "Both methods", SHARED_COLOUR),
                        (unique[method], f"{method} only", METHOD_COLOURS[method]),
                    )
                    if ids
                ]
                panel.set_trip(od_pair, results[method], comparison_view, overlays)
            closure_view = (
                map_view(trip_geometry) if not trip_geometry.empty else zone_view
            )
            closure.set_trip(od_pair, results, closure_view)
            status.value = ""
        finally:
            run.disabled = False

    run.on_click(update_trip)
    update_trip(None)
    controls = widgets.HBox(
        [origin, destination, run], layout={"flex_flow": "row wrap"}
    )
    return widgets.VBox([controls, status, tabs])
