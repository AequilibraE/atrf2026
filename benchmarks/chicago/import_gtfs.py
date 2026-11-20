"""Import the CTA, Metra and Pace GTFS feeds into the Chicago model.

Uses AequilibraE 2.0.0rc1. All three feeds run the same weekday service on every
Tuesday from 2023-09-26 to 2023-11-21, so a single date is used for all of them.
Route shapes come from each feed's shapes.txt, so no map-matching is done.

    python import_gtfs.py [model_folder]

The importer creates public_transport.sqlite in the model folder and refuses to
run if that file already exists. Delete it to import again.
"""

import sys
from pathlib import Path

from aequilibrae import Project, __version__
from aequilibrae.transit.transit_elements.link import Link

# Workaround for 2.0.0rc1: Link.build_geo divides the shape-segment length by the straight-line
# length between the two stops, which is zero when consecutive stops share coordinates. CTA rail
# has six such platform pairs (e.g. 30026 -> 30027). Keep the direct line for those, which is what
# the library's "shape segment longer than 2x the straight line" rule picks for any positive length.
_build_geo = Link.build_geo


def _build_geo_coincident_stops(self, from_point, to_point, gtfs_shape, previous_end, start=0):
    if from_point.equals(to_point):
        gtfs_shape = None
    return _build_geo(self, from_point, to_point, gtfs_shape, previous_end, start)


Link.build_geo = _build_geo_coincident_stops

MODEL = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "model"
GTFS_FOLDER = Path(r"D:\OL\src\geolibre_gtfs\GTFS_examples")
SERVICE_DATE = "2023-10-17"  # Tuesday

FEEDS = {
    "CTA": "cta_2023_09_27.zip",
    "Metra": "metra_2023_09_29.zip",
    "Pace": "pace_2023_0924.zip",
}

transit_db = MODEL / "public_transport.sqlite"
if transit_db.exists():
    sys.exit(f"{transit_db} already exists. Delete it to import the feeds again.")

print(f"AequilibraE {__version__}, model: {MODEL.resolve()}, service date: {SERVICE_DATE}")

try:
    with Project(MODEL) as project:
        transit = project.scenario.create_transit_database()

        for agency, file_name in FEEDS.items():
            feed = transit.new_gtfs_builder(
                agency=agency,
                file_path=str(GTFS_FOLDER / file_name),
                description=f"{agency} GTFS ({file_name}), service on {SERVICE_DATE}",
            )
            feed.load_date(SERVICE_DATE)
            feed.save_to_disk()
            print(
                f"{agency}: {len(feed.select_routes)} routes, {len(feed.select_patterns)} patterns, "
                f"{len(feed.select_trips)} trips, {len(feed.select_stops)} stops"
            )
except BaseException:
    transit_db.unlink(missing_ok=True)  # do not leave a partial import behind
    raise
