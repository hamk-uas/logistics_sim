import numpy as np
import waste_pickup_sim
import json

sim_config = {	
	'vehicle_template': {
		'load_capacity': 18, # Tonnes
		'max_shift_duration': 9*60, # Minutes 
		'break_duration': 45, # Minutes # Break Happens after 1/2 of drivetime 
		'num_breaks_per_shift': 1,
		'pickup_duration': 15 # Minutes
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
	'sim_runtime_days': 14, # Simulation runtime in days
	'pickup_sites_filename': 'geo_data/sim_test_sites.geojson',
	'depots_filename': 'geo_data/sim_test_terminals.geojson',
	'terminals_filename': 'geo_data/sim_test_terminals.geojson'
}

waste_pickup_sim.preprocess_sim_config(sim_config)
sim = waste_pickup_sim.WastePickupSimulation(sim_config)