from aequilibrae import Project, Graph
from aequilibrae.paths import TrafficAssignment, TrafficClass
import numpy as np
from aequilibrae import logger


def assignment(proj: Project, carGraph: Graph, truckGraph: Graph, periods: list[str]):

    results = {}
    for period in periods:
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
        assig.max_iter = 2000
        assig.rgap_target = 1e-5
        # assig.steps_below_needed_to_terminate = 1
        assig.set_algorithm('bfw')

        assig.execute()  # we then execute the assignment

        results[period] = assig
    return results
