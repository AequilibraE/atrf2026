import numpy as np

from aequilibrae import Project


def format_matrices(project: Project):
    for file_name in project.matrices.list().index:
        with project.matrices.get_matrix(file_name) as store:
            if "AUTO" in store:
                continue
            car_names = [name for name in store if name not in {"COMMTRK", "HTRK"}]
            all_cars = np.zeros(store.shape, dtype=np.float64)
            for name in car_names:
                all_cars += store[name]

        with project.matrices.get_matrix(file_name, mode="r+") as store:
            store["AUTO"] = all_cars
