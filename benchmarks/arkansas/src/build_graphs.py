def build_graphs(proj):
    net = proj.network
    modes = net.modes
    modes.all_modes()

    with proj.db_connection as conn:
        conn.execute("update nodes set is_centroid = 0 where node_id in (4701, 4702, 4703)")

    net.build_graphs(modes=['T'])
    truckGraph = net.graphs['T']
    net.build_graphs(modes=['c'])
    carGraph = net.graphs['c']

    # Link exclusions
    with proj.db_connection as conn:
        sql = "select link_id from links where exclusionset IN ('TruckOnly', 'HOV2', 'HOV3')"
        exclude_from_passenger = [x[0] for x in conn.execute(sql).fetchall()]

        sql = "select link_id from links where exclusionset IN ('PassengerOnly', 'HOV2', 'HOV3')"
        exclude_from_truck = [x[0] for x in conn.execute(sql).fetchall()]


    graph = truckGraph
    set1 = graph.network[
        (graph.network.builtyear > 2010) | (graph.network.removedyear < 2010)
        | (graph.network.builtyear.isna() & graph.network.removedyear.isna())
    ].link_id.to_list()
    set2 = graph.network[(graph.network.mode_code <10) | (graph.network.mode_code >11)].link_id.to_list()
    exclude_from_passenger.extend(set1 + set2)
    exclude_from_truck.extend(set1 + set2)

    truckGraph.exclude_links(exclude_from_truck)
    carGraph.exclude_links(exclude_from_passenger)

    with proj.db_connection as conn:
        conn.execute("update nodes set is_centroid = 0 where node_id in (4701, 4702, 4703)")

    for graph in [carGraph, truckGraph]:
        graph.network.alpha_ab = graph.network.alpha_ab.fillna(0.15)
        graph.network.alpha_ba = graph.network.alpha_ba.fillna(0.15)
        
        graph.network.beta_ab = graph.network.beta_ab.fillna(4.0)
        graph.network.beta_ba = graph.network.beta_ba.fillna(4.0)
        graph.network.hov1tollcost = graph.network.hov1tollcost.fillna(0)
        graph.network.mttollcost = graph.network.mttollcost.fillna(0)
        graph.network.httollcost = graph.network.httollcost.fillna(0)

        for period in ['am', 'pm', 'md', 'nt']:
            graph.network.loc[graph.network.a_node == graph.network.b_node, f"{period}_assncap_10_ab"] = 1.0
            graph.network.loc[graph.network.a_node == graph.network.b_node, f"{period}_assncap_10_ba"] = 1.0
            graph.network.loc[graph.network.a_node == graph.network.b_node, f"tt_{period}_10_ab"] = 0.001
            graph.network.loc[graph.network.a_node == graph.network.b_node, f"tt_{period}_10_ba"] = 0.001
    
        graph.prepare_graph(graph.centroids)


    return carGraph, truckGraph