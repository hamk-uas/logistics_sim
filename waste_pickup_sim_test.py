import json
import waste_pickup_sim

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

#with open("") as f:
#    gj = geojson.load(f)
#features = gj['features'][0]

sim = waste_pickup_sim.WastePickupSimulation(sim_config)
sim.simulate()
