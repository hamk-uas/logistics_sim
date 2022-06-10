import math
import numpy as np
import simpy
import random


TRUCK_CAPACITY = 6
N_TRUCKS = 2


# Create init distance matrix
def create_random_distance_matrix(num_locations, min, max, symmetrical=True):
	""""""
	num_distances = num_locations*(num_locations - 1)//2
	distance_matrix = np.zeros((num_locations, num_locations), dtype=int)

	if symmetrical:
		distance_array = np.random.randint(min, max, size=(num_distances))
   		# create the distance matrix
		distance_matrix[np.triu_indices(num_locations, k=1)] = distance_array
		distance_matrix += distance_matrix.T

	if not symmetrical:
		distance_matrix[np.triu_indices(num_locations, k=1)] = np.random.randint(min, max, size=(num_distances))
		distance_matrix[np.tril_indices(num_locations, k=-1)] = np.random.randint(min, max, size=(num_distances))

	return distance_matrix


class WastePickupSite(simpy.Container):
	""""""

	index = None

	def __init__(self, env, index, capacity, initial_load):
		self.index = index
		simpy.Container.__init__(env, capacity=capacity)
		self.put(initial_load)
		print(f"On waste site #{index} there are currently {initial_load} tons at {env.now}")

def pick_up_load(env, name, load, site, gray_sites, distance_matrix):
	""""""
	
	yield env.timeout(distance_matrix[0][site]) # Drive time here
	print(f"Truck {name} arrives to {site} at {env.now}")
	yield env.timeout(5) # Picking up time
	available_space = TRUCK_CAPACITY - load['current_load']
	if gray_sites[str(site)].level >= available_space:
		to_pick_up = available_space
	else:
		to_pick_up = gray_sites[str(site)].level


	yield gray_sites[str(site)].get(to_pick_up)

	print(f"Truck {name} picks up {to_pick_up} tonns on {site} at {env.now}")
	print(f"{gray_sites[str(site)].level} tonns left on gray site {site}")

	load['current_load'] += to_pick_up
	print(f"Truck {name} now has {load['current_load']} tonns at {env.now}")
	if load['current_load'] == TRUCK_CAPACITY:
			print(f"Truck {name} enroute to DEPOT at {env.now}")
			yield env.process(drop_load(env, name, load, site, distance_matrix))

	

def drop_load(env, name, load, site, distance_matrix):
	""""""
	
	yield env.timeout(distance_matrix[site][0]) # Drive to base
	print(f"Truck {name} arrives to DEPOT at {env.now}")
	yield env.timeout(5) #Drop off time
	print(f"Truck {name} drops {load['current_load']} tonns on DEPOT at {env.now}")
	load['current_load'] = 0


def gray_truck_route(env, name, route, gray_sites, distance_matrix):
	"""
	"""
	load = {'current_load':0}
	print(f"Truck {name} embarks on {route} at {env.now}")
	for site in route:
		print(f"Truck {name} enroute to {site} at {env.now}")
		yield env.process(pick_up_load(env, name, load, site, gray_sites, distance_matrix))


		if gray_sites[str(site)].level != 0:
			yield env.process(pick_up_load(env, name, load, site, gray_sites, distance_matrix))

class DayShiftSimulationModel:	
    '''
	Simulation of a day shift
    '''

	num_vehicles = None
	vehicle_capacity = None

	distance_matrix = None

	num_waste_pickup_sites = None	
	waste_pickup_site_capacities = None

	waste_pickup_duration = None
	waste_drop_off_duration = None

	depot_location_index = 0
	sink_location_index = 1
	first_waste_pickup_site_location_index = 2

	def plan_vehicle_route():
		full_route = np.array([self.depot_location_index]).append(self.first_waste_pickup_site_location_index + np.random.permutation(self.num_waste_pickup_sites)).append(self.sink_location_index)
		return full_route[:3]

	def gray_shift(env, route, vehicle_index):
		"""
		"""

		gray_sites = waste_sites(env, sites)

		route_shift = env.process(gray_truck_route(env, vehicle_index, route, gray_sites))

		yield env.timeout(0)

	def __init__(**sim_config):
		self.num_vehicles = sim_config["num_vehicles"]
		self.vehicle_capacity = sim_config["vehicle_capacity"]
		self.distance_matrix = create_random_distance_matrix(num_locations=1+sim_config["num_waste_pickup_sites"]+1,
			min=sim_config["distance_matrix"][1], max=sim_config["distance_matrix"][2])
		self.something = 123		

	def run():
		env = simpy.Environment()

		for i in range(self.num_waste_pickup_sites):
			WastePickupSite(self, env, index, capacity, initial_load)

		for i in range(self.num_vehicles):
			route = self.plan_vehicle_route()
			shift = env.process(gray_shift(env, self.distance_matrix, route, i))

		env.run()

sim_config = {
	'num_vehicles': 2,
	'vehicle_capacity': [6, 6], #Unit is metric tonnes

	'num_waste_pickup_sites': 5,
	'waste_pickup_site_capacity': [5, 5, 5, 5, 5], # Unit is metric tonnes

	'distance_matrix': ['random', 5, 25], # Unit is minutes

	'waste_pickup_duration': None,
	'waste_drop_off_duration': None,	
}

simulation = DayShiftSimulationModel(**sim_config)
simulation.run()