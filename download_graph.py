# download_graph.py — run once to pre-download the road graph
import osmnx as ox

print("Downloading Hyderabad road graph... please wait ~2 min")
G = ox.graph_from_place("Hyderabad, Telangana, India", network_type="walk")
ox.save_graphml(G, "hyderabad_walk.graphml")
print("Done! File saved as hyderabad_walk.graphml")