import numpy as np
import waste_pickup_sim
import json

sim_config = {	
	'sim_name': 'Hämeenlinna and nearby regions',
	'sim_runtime_days': 14, #14, # Simulation runtime in days
	'pickup_sites_filename': 'geo_data/sim_test_sites.geojson',
	'depots_filename': 'geo_data/sim_test_terminals.geojson',
	'terminals_filename': 'geo_data/sim_test_terminals.geojson',
	'vehicle_template': {
		'load_capacity': 18, # Tonnes
		'max_route_duration': 8*60 + 15, # Minutes (9h - 45min break = 8h 15min)
#		'break_duration': 45, # Minutes # Break Happens after 1/2 of drivetime 
#		'num_breaks_per_shift': 1,
		'pickup_duration': 15 # Minutes
	},
	'depots': [
		{
			'num_vehicles': 2
		},
		{
			'num_vehicles': 2
		}
	]
}

waste_pickup_sim.preprocess_sim_config(sim_config, 'sim_config.json')
sim = waste_pickup_sim.WastePickupSimulation(sim_config)
sim.sim_run()