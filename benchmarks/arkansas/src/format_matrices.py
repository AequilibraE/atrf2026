from os.path import join
import openmatrix as omx


def format_matrices(proj):
    proj_matrices = proj.matrices
    mat_list = proj_matrices.list()

    auto = 'AUTO'
    for idx, mat_record in mat_list.iterrows():
        rec = proj_matrices.get_record(mat_record['name'])
        
        demand = proj_matrices.get_matrix(mat_record['name'])
        if auto in demand.names:
            continue
        cores = [core for core in demand.names if core not in ['COMMTRK', 'HTRK']]
        demand.computational_view(cores)
        all_cars = demand.matrix_view.sum(axis=2)
        demand.close()
        omx_file = omx.open_file(join(rec.fldr, rec.file_name), 'a')
        omx_file[auto] = all_cars
        omx_file.close()
    del demand