import numpy as np
import json
import waste_pickup_sim
from geopy.distance import geodesic

sim_config = {	
	"pickup_site": {
		"capacity_range" : [10, 20], # tonnes
		"deadline_offset": 7*24*60 # minutes
	},
	"vehicle": {
		'load_capacity' : 18, # Tonnes
		'max_shift_duration' : 540, # Minutes 
		'break_duration' : 45, # Minutes # Break Happens after 1/2 of drivetime 
		'num_breaks_per_shift' : 1,
		'pickup_duration' : 15 # Minutes
	},
	"pickup_site_operator": {
	},
	"fleet_operator": {
		'num_vehicles': 2,
		'relative_level_threshold_for_pickup' : 0.8  # When the container level reaches this value expressed relative to capacity, order a pickup to be done as soon as possible
	},
	"area": {
		'name' : 'Turku',
		'drivetime_range' : [5, 60], # Minutes
		'num_pickup_sites' : 10, # N
		'num_terminals': 2,
		'num_depots': 2,
	},
	"sim": {
		'runtime_days' : 14 # Simulation runtime in days
	}
}

# Init area config without places
sim_config["area"]["place_coordinates"] = []
sim_config["area"]["places"] = []
sim_config["area"]["num_places"] = 0

# Extract pickup site coordinates
with open("geo_data/sim_test_sites.geojson") as pickup_sites_file:
    pickup_sites_geojson = json.load(pickup_sites_file)
for pickup_site in pickup_sites_geojson["features"]:
	pickup_site["properties"]["sim_place_index"] = sim_config["area"]["num_places"]
	sim_config["area"]["places"].append(pickup_site)
	sim_config["area"]["place_coordinates"].append(tuple(pickup_site["geometry"]["coordinates"]))
	sim_config["area"]["num_places"] += 1
sim_config["pickup_sites"] = pickup_sites_geojson["features"]

# Extract terminal coordinates.
with open("geo_data/sim_test_terminals.geojson") as terminals_file:
     terminals_geojson = json.load(terminals_file)
for terminal in terminals_geojson["features"]:
	terminal["properties"]["sim_place_index"] = sim_config["area"]["num_places"]
	sim_config["area"]["places"].append(terminal)
	sim_config["area"]["place_coordinates"].append(tuple(terminal["geometry"]["coordinates"]))
	sim_config["area"]["num_places"] += 1
sim_config["terminals"] = terminals_geojson["features"]

# Extract depot coordinates (we don't know those yet so use terminal coordinates)
with open("geo_data/sim_test_terminals.geojson") as depots_file:
     depots_geojson = json.load(depots_file)
for depot in depots_geojson["features"]:
	depot["properties"]["sim_place_index"] = sim_config["area"]["num_places"]
	sim_config["area"]["places"].append(depot)
	sim_config["area"]["place_coordinates"].append(tuple(depot["geometry"]["coordinates"]))
	sim_config["area"]["num_places"] += 1
sim_config["depots"] = depots_geojson["features"]

#print(geodesic(sim_config["area"]["place_coordinates"][-2], sim_config["area"]["place_coordinates"][-1]))

print("Number of places:")
print(sim_config["area"]["num_places"])

print("Calculating geodesic distance matrix...")
sim_config["area"]["distance_matrix"] = np.ndarray((sim_config["area"]["num_places"], sim_config["area"]["num_places"]), dtype=np.float32)
for b_index, b in enumerate(sim_config["area"]["place_coordinates"]):
	for a_index, a in enumerate(sim_config["area"]["place_coordinates"]):
		sim_config["area"]["distance_matrix"][b_index, a_index] = geodesic(a, b).km
print("Done")
print(sim_config["area"]["distance_matrix"])

sim = waste_pickup_sim.WastePickupSimulation(sim_config)
#sim.simulate()
