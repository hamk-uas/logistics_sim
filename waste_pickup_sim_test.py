import numpy as np
import json
import waste_pickup_sim
import random
from geopy.distance import geodesic

sim_config = {	
	'vehicle': {
		'load_capacity' : 18, # Tonnes
		'max_shift_duration' : 9*60, # Minutes 
		'break_duration' : 45, # Minutes # Break Happens after 1/2 of drivetime 
		'num_breaks_per_shift' : 1,
		'pickup_duration' : 15 # Minutes
	},
	'depots': [
		{
			'num_vehicles': 2
		},
		{
			'num_vehicles': 2
		}
	],
	'sim_name' : 'Turku',
	'sim_runtime_days' : 14 # Simulation runtime in days
}

# Init area config without locations
sim_config['location_coordinates'] = []
sim_config['locations'] = []
sim_config['num_locations'] = 0

# Create configurations for pickup sites using known data and random values
sim_config['pickup_sites'] = []
with open('geo_data/sim_test_sites.geojson') as pickup_sites_file:
    pickup_sites_geojson = json.load(pickup_sites_file)
for pickup_site in pickup_sites_geojson['features']:
	pickup_site_config = {
		**pickup_site['properties'],
		'coordinates': tuple(pickup_site['geometry']['coordinates']),
		'capacity': random.uniform(10, 20)
	}
	pickup_site_config['daily_growth_rate'] = pickup_site_config['capacity']*np.random.lognormal(np.log(1 / ((14 + 21) / 2)), 0.1) # Log-normal dist of 2 to 3 weeks to be full.
	sim_config['pickup_sites'].append(pickup_site_config)

# Create configurations for terminals and depots using known data and random values
sim_config['terminals'] = []
with open('geo_data/sim_test_terminals.geojson') as terminals_file:
     terminals_geojson = json.load(terminals_file)
for terminal in terminals_geojson['features']:
	terminal['properties']['sim_location_index'] = sim_config['num_locations']
	terminal_config = {
		**terminal['properties'],
		'coordinates': tuple(terminal['geometry']['coordinates'])
	}
	# We don't know depot locations. Assume they are the same as terminal locations
	sim_config['depots'][len(sim_config['terminals'])]['coordinates'] = tuple(terminal['geometry']['coordinates'])
	sim_config['terminals'].append(terminal_config)

with open('sim_config.json', 'w') as outfile:
    outfile.write(json.dumps(sim_config, indent=4))

# Create simulation. It will index all locations to sim.locations
sim = waste_pickup_sim.WastePickupSimulation(sim_config)

# Calculate geodesic distance matrix
print("Calculating geodesic distance matrix...")
distance_matrix = np.ndarray((len(sim.locations), len(sim.locations)), dtype=np.float32)
for b_index, b in enumerate(sim.locations):
	for a_index, a in enumerate(sim.locations):
		distance_matrix[b_index, a_index] = geodesic(a, b).km
print("Done")

sim.sim_init(distance_matrix)
#sim.sim_run()

routing_input = {
	'distance_matrix': sim.area_config['distance_matrix'].tolist(),
	'pickup_sites': list(map(lambda x: {
		'capacity': x.capacity,
		'level': x.level,
		'growth_rate': x.daily_growth_rate/(24*60)
	}, sim.pickup_sites))
}

with open('routing_input.json', 'w') as outfile:
    outfile.write(json.dumps(routing_input, indent=4))

