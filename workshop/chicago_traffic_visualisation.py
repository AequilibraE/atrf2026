"""Show traffic volumes and volume-to-capacity ratios on the Chicago road network."""

import geopandas as gpd
import ipywidgets as widgets
import numpy as np
from lonboard import PathLayer

from route_choice_visualisation import WorkshopMap, make_zone_layer, map_view

MAP_HEIGHT = 540
VOC_OPTIONS = {"Maximum": "VOC_max", "A to B": "VOC_AB", "B to A": "VOC_BA"}
VOC_BREAKS = (0.5, 0.8, 1.0)
VOC_LABELS = (
    "Below 0.5",
    "0.5 to below 0.8",
    "0.8 to below 1.0",
    "1.0 or more",
    "No data",
)
VOC_COLOURS = np.array(
    [(38, 128, 123), (199, 154, 51), (215, 97, 34), (173, 36, 56), (143, 151, 162)],
    dtype=np.uint8,
)
CORDON_COLOUR = (229, 91, 53)


def _voc_legend(show_no_data):
    labels = VOC_LABELS if show_no_data else VOC_LABELS[:-1]
    swatches = []
    for label, colour in zip(labels, VOC_COLOURS):
        rgb = ", ".join(map(str, colour))
        swatches.append(
            f'<span style="white-space: nowrap"><span style="color: rgb({rgb})" '
            f'aria-hidden="true">●</span> {label}</span>'
        )
    return widgets.HTML(
        "<b>Volume-to-capacity ratio</b> &nbsp; " + " &nbsp; ".join(swatches)
    )


def show_link_results(links, results, zones, *, volume_options=None, cordon=None):
    """Show zones and colour roads by VoC, with optional volume widths and a cordon."""
    voc_options = {"Maximum": "VOC_max"} if volume_options else VOC_OPTIONS
    volume_options = volume_options or {}
    values = links[["link_id", "link_type", "direction", "geometry"]].join(
        results[list(voc_options.values()) + list(volume_options.values())],
        on="link_id",
        validate="one_to_one",
    )
    if not volume_options:
        # The assignment reports zero for directions that a link does not allow.
        values["VOC_AB"] = values["VOC_AB"].mask(values["direction"] == -1)
        values["VOC_BA"] = values["VOC_BA"].mask(values["direction"] == 1)

    def colours(column):
        ratios = values[column].to_numpy()
        bands = np.digitize(ratios, VOC_BREAKS)
        bands[np.isnan(ratios)] = len(VOC_LABELS) - 1
        return VOC_COLOURS[bands]

    picker = widgets.Dropdown(
        options=volume_options or voc_options,
        description="Volume" if volume_options else "VoC",
        layout=widgets.Layout(width="min(285px, 100%)"),
        style={"description_width": "auto"},
    )
    if volume_options:
        volume = values[list(volume_options.values())].fillna(0)
        widths = (14 * volume / max(1, volume.max().max())).astype("float32")
        width = widths[picker.value].to_numpy()
        colour = colours("VOC_max")
    else:
        width = 1.7
        colour = colours(picker.value)

    tooltip_names = {
        "link_id": "Link ID",
        "link_type": "Link type",
        **{column: f"{label} VoC" for label, column in voc_options.items()},
        **{column: label for label, column in volume_options.items()},
    }
    map_links = (
        values[list(tooltip_names) + ["geometry"]]
        .round(2)
        .rename(columns=tooltip_names)
    )
    layer = PathLayer.from_geopandas(
        map_links,
        get_width=width,
        get_color=colour,
        width_units="pixels",
        auto_highlight=True,
    )

    def update_metric(change):
        if volume_options:
            layer.get_width = widths[change["new"]].to_numpy()
        else:
            layer.get_color = colours(change["new"])

    picker.observe(update_metric, names="value")

    zone_data = zones[["zone_id", "geometry"]].rename(columns={"zone_id": "Zone ID"})
    zone_layer = make_zone_layer(zone_data)
    show_zones = widgets.Checkbox(
        description="Zones", value=True, indent=False, layout={"width": "auto"}
    )
    show_zones.observe(
        lambda change: setattr(zone_layer, "visible", change["new"]), names="value"
    )

    layers = [zone_layer, layer]
    legend_items = [_voc_legend(show_no_data=not volume_options)]
    if cordon is not None:
        boundary = gpd.GeoDataFrame(geometry=[cordon.boundary], crs=links.crs)
        layers.append(
            PathLayer.from_geopandas(
                boundary,
                get_color=list(CORDON_COLOUR),
                get_width=2.5,
                width_units="pixels",
                pickable=False,
            )
        )
        rgb = ", ".join(map(str, CORDON_COLOUR))
        legend_items.append(
            widgets.HTML(
                f'<span style="color: rgb({rgb})" aria-hidden="true">━</span> Cordon'
            )
        )

    traffic_map = WorkshopMap(
        layers=layers,
        basemap=None,
        height=MAP_HEIGHT,
        show_side_panel=False,
        show_tooltip=True,
    )
    zone_view = map_view(zone_data.geometry.to_crs(3857), height=MAP_HEIGHT)
    fit_zones = widgets.Button(description="Fit zones", layout={"width": "100px"})

    def fit_to_zones(_):
        show_zones.value = True
        traffic_map.set_view_state(**zone_view, pitch=0, bearing=0)

    fit_zones.on_click(fit_to_zones)
    toolbar = widgets.HBox(
        [picker, show_zones, fit_zones],
        layout={"flex_flow": "row wrap", "align_items": "center"},
    )
    legend = widgets.HBox(
        legend_items,
        layout={"flex_flow": "row wrap", "align_items": "center"},
    )
    return widgets.VBox([toolbar, legend, traffic_map])
