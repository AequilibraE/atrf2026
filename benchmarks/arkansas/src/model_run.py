import argparse
from pathlib import Path

from aequilibrae import Project
from aequilibrae.utils import basic_config

if __package__:
    from .assignments import assign_period
    from .build_graphs import PERIODS, build_network
else:
    from assignments import assign_period
    from build_graphs import PERIODS, build_network


def main():
    parser = argparse.ArgumentParser(description="Run the Arkansas traffic assignments.")
    parser.add_argument("model_path", type=Path, nargs="?", default=Path("/mnt/d/models/Arkansas/model"))
    args = parser.parse_args()

    basic_config()
    with Project(args.model_path) as project:
        network = build_network(project)
        for period in PERIODS:
            is_night = period == "nt"
            assign_period(
                project,
                network,
                period,
                algorithm="msa" if is_night else "bfw",
                max_iterations=200,
                rgap=1e-6 if is_night else 1e-5,
            )


if __name__ == "__main__":
    main()
