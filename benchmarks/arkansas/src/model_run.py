from os.path import join
from aequilibrae import Project
from aequilibrae.paths import TrafficAssignment, TrafficClass
import logging
import sys

import numpy as np
from aequilibrae import logger

pth = "D:/OL/UARK/model"

proj = Project()
proj.open(pth)
net = proj.network
curr = proj.conn.cursor()

stdout_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s ; %(levelname)s ; %(message)s")
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)

proj_matrices = proj.matrices
mat_list = proj_matrices.list()

modes = net.modes
modes.all_modes()

nodes = net.nodes

for n in [4701, 4702, 4703]:
    nd = nodes.get(n)
    nd.is_centroid = 0
    nd.save()

net.build_graphs(modes=['T'])
truckGraph = net.graphs['T']
net.build_graphs(modes=['c'])
carGraph = net.graphs['c']

# Link exclusions
curr.execute("select link_id from links where exclusionset IN ('TruckOnly', 'HOV2', 'HOV3')")
exclude_from_passenger = [x[0] for x in curr.fetchall()]

curr.execute("select link_id from links where exclusionset IN ('PassengerOnly', 'HOV2', 'HOV3')")
exclude_from_truck = [x[0] for x in curr.fetchall()]


graph = truckGraph
set1 = graph.network[(graph.network.builtyear > 2010) | (graph.network.removedyear < 2010)].link_id.to_list()
set2 = graph.network[(graph.network.mode_code <10) | (graph.network.mode_code >11)].link_id.to_list()
exclude_from_passenger.extend(set1 + set2)
exclude_from_truck.extend(set1 + set2)

truckGraph.exclude_links(exclude_from_truck)
carGraph.exclude_links(exclude_from_passenger)

nodes = net.nodes
for n in [4701, 4702, 4703]:
    nd = nodes.get(n)
    nd.is_centroid = 1
    nd.save()

for graph in [carGraph, truckGraph]:
    graph.graph.alpha.fillna(0.15, inplace=True)
    graph.graph.beta.fillna(4.0, inplace=True)
    graph.graph.hov1tollcost.fillna(0, inplace=True)
    graph.graph.mttollcost.fillna(0, inplace=True)
    graph.graph.httollcost.fillna(0, inplace=True)
    for period in ['am', 'pm', 'md', 'nt']:
        graph.graph.loc[graph.graph.a_node == graph.graph.b_node, f"{period}_assncap_10"] = 1.0
        graph.graph.loc[graph.graph.a_node == graph.graph.b_node, f"tt_{period}_10"] = 0.001

# proj.conn.execute('delete from results')
# proj.conn.commit()

for period in ['am', 'md', 'pm', 'nt']:
    logger.info(f'\n\n Assigning {period.upper()}')
    proj_matrices = proj.matrices
    carDemand = proj_matrices.get_matrix(f'{period.upper()}_omx')
    carDemand.computational_view('AUTO')

    lightTruckDemand = proj_matrices.get_matrix(f'{period.upper()}_omx')
    lightTruckDemand.computational_view('COMMTRK')
    lightTruckDemand.matrix_view = np.array(lightTruckDemand.matrix_view, np.float64)

    heavyTruckDemand = proj_matrices.get_matrix(f'{period.upper()}_omx')
    heavyTruckDemand.computational_view('HTRK')
    heavyTruckDemand.matrix_view = np.array(heavyTruckDemand.matrix_view, np.float64)

    assig = TrafficAssignment()
    assig.procedure_id = f'{period}_baseline'
    carClass = TrafficClass('car', carGraph, carDemand)
    carClass.set_pce(1)
    carClass.set_vot(0.2)
    carClass.set_fixed_cost('hov1tollcost')

    # The link exclusions for commercial trucks are actually the same as the ones for passenger cars, and not heavy trucks
    lightTruckClass = TrafficClass('light_truck', carGraph, lightTruckDemand)
    lightTruckClass.set_pce(1.5)
    lightTruckClass.set_vot(0.5)
    lightTruckClass.set_fixed_cost("mttollcost")

    heavyTruckClass = TrafficClass('heavy_truck', truckGraph, heavyTruckDemand)
    heavyTruckClass.set_pce(2.5)
    heavyTruckClass.set_vot(1.0)
    heavyTruckClass.set_fixed_cost("httollcost")

    # The first thing to do is to add at list of traffic classes to be assigned
    assig.set_classes([heavyTruckClass, carClass, lightTruckClass])
    assig.set_vdf("BPR")  # This is not case-sensitive # Then we set the volume delay function

    assig.set_vdf_parameters({"alpha": "alpha", "beta": "beta"})  # And its parameters

    assig.set_time_field(f"tt_{period}_10")
    assig.set_capacity_field(f"{period}_assncap_10")  # The capacity and free flow travel times as they exist in the graph

    # And the algorithm we want to use to assign
    if period == 'nt':
        assig.set_algorithm('msa')
        assig.max_iter = 200
        assig.rgap_target = 0.000001
    else:
        assig.set_algorithm('bfw')
        assig.max_iter = 200
        assig.rgap_target = 0.00001

    assig.set_save_path_files(False)

    assig.execute()  # we then execute the assignment


    # carGraph.graph.to_feather(join(pth, 'path_files', assig.procedure_id, f'{carClass.__id__}_graph.feather'))
    # carGraph.compact_graph.to_feather(join(pth, 'path_files', assig.procedure_id, f'{carClass.__id__}compact_graph.feather'))

    # carGraph.graph.to_feather(join(pth, 'path_files', assig.procedure_id, f'{lightTruckClass.__id__}_graph.feather'))
    # carGraph.compact_graph.to_feather(join(pth, 'path_files', assig.procedure_id, f'{lightTruckClass.__id__}compact_graph.feather'))

    # truckGraph.graph.to_feather(join(pth, 'path_files', assig.procedure_id, f'{heavyTruckClass.__id__}_graph.feather'))
    # truckGraph.compact_graph.to_feather(join(pth, 'path_files', assig.procedure_id, f'{heavyTruckClass.__id__}compact_graph.feather'))

    # assig.save_results(f'assign_{period}_gen_cost_path_file')

proj.close()