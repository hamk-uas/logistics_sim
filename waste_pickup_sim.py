import math
import simpy
import random
import numpy as np
import queue as queue
import json
import random
import functools
from geopy.distance import geodesic

from get_distance_matrix import request_distance_matrix


def time_to_string(minutes):
	hours = math.floor(minutes/60)
	minutes -= hours*60
	days = math.floor(hours/24)
	hours -= days*24
	return f"{str(days):>3}d {str(hours).zfill(2)}:{str(minutes).zfill(2)}"

def tons_to_string(tons):
	return f"{tons:.3f}t"

def to_percentage_string(number):
	return f"{number*100:.0f}%"


def heuristic_router(routing_input):
#    "pickup_sites": [
#        {
#            "capacity": 2,
#            "level": 0.9848136938048543,
#            "growth_rate": 8.10984801062072e-05	

	# Sort sites based on when they become full
	indexes_and_times_when_full = []
	for pickup_site_index, pickup_site in enumerate(routing_input['pickup_sites']):
		time_when_full = (pickup_site['capacity'] - pickup_site['level'])/pickup_site['growth_rate']
		indexes_and_times_when_full.append((pickup_site_index, time_when_full))
	indexes_and_times_when_full.sort(key=lambda index_and_time_when_full: index_and_time_when_full[1])

	# Assign destinations to vehicles, in interleaved order so that every vehicle gets the same number of sites
	vehicle_routes = []

	for vehicle in routing_input['vehicles']:
		home_depot = routing_input['depots'][vehicle['home_depot_index']]
		vehicle_routes.append([home_depot['location_index']])

	vehicle_route_durations = [0 for _ in range(len(routing_input['vehicles']))]
	durations_back_home = [0 for _ in range(len(routing_input['vehicles']))]
	for index, pickup_site_index_and_time_when_full in enumerate(indexes_and_times_when_full):
		vehicle_index = index % len(routing_input['vehicles'])
		vehicle = routing_input['vehicles'][vehicle_index]
		home_depot_location_index = routing_input['depots'][vehicle['home_depot_index']]['location_index']
		proposed_location_index = routing_input['pickup_sites'][pickup_site_index_and_time_when_full[0]]['location_index']
		# Calculate proposed route duration
		to_proposed_location_duration = routing_input['duration_matrix'][vehicle_routes[vehicle_index][-1]][proposed_location_index]
		from_proposed_location_to_home_depot_duration = routing_input['duration_matrix'][proposed_location_index][home_depot_location_index]
		proposed_route_duration = vehicle_route_durations[vehicle_index] + to_proposed_location_duration + from_proposed_location_to_home_depot_duration
		if proposed_route_duration <= vehicle['max_route_duration']:
			vehicle_routes[vehicle_index].append(proposed_location_index)
			vehicle_route_durations[vehicle_index] += to_proposed_location_duration
			durations_back_home[vehicle_index] = from_proposed_location_to_home_depot_duration

	for vehicle_index, vehicle in enumerate(routing_input['vehicles']):
		home_depot = routing_input['depots'][vehicle['home_depot_index']]
		vehicle_routes[vehicle_index].append(home_depot['location_index'])
		vehicle_route_durations[vehicle_index] += durations_back_home[vehicle_index]

	routing_output = {
		'vehicles': [{
			'route': route
		} for route in vehicle_routes]
	}
	
	print(routing_output)

	return routing_output

class PickupSite():

	def log(self, message):
		self.sim.log(f"Pickup site #{self.index}: {message}")

	def warn(self, message):
		self.sim.warn(f"Pickup site #{self.index}: {message}")

	def __init__(self, sim, index):
		self.sim = sim
		self.index = index
		self.location_index = self.sim.config['pickup_sites'][self.index]['location_index']

		self.capacity = self.sim.config['pickup_sites'][index]['capacity']
		self.level = self.sim.config['pickup_sites'][index]['level']
		self.levelListeners = []

		self.daily_growth_rate = self.sim.config['pickup_sites'][index]['daily_growth_rate']
		self.log(f"Initial level: {tons_to_string(self.level)} of {tons_to_string(self.capacity)} ({to_percentage_string(self.level / self.capacity)}), growth rate: {tons_to_string(self.daily_growth_rate)}/day")

		self.growth_process = sim.env.process(self.grow_daily_forever())

	def put(self, amount):
		listeners_to_message_maybe = list(filter(lambda x: self.level < x[1], self.levelListeners))
		self.level += amount
		listeners_to_message = list(filter(lambda x: self.level >= x[1], listeners_to_message_maybe))
		if len(listeners_to_message):
			self.log(f"Level increase past threshold for {len(listeners_to_message)} listeners.")
		for x in listeners_to_message:
			x[0](**x[2])

	def estimate_when_full():
		# Solve:
		# { level_at_time_x = level_now + (time_x - time_now)*growth_rate
		# { capacity = level_at_time_x
		# => capacity = level_now + (time_x - time_now)*growth_rate
		# => time_x = time_now + (capacity - level_now)/growth_rate
		return self.sim.env.now + 24*60*(self.capacity - self.level)/self.daily_growth_rate

	def addLevelListener(self, listener, threshold, data = None):
		#self.log("Added level listener")
		listener_info = (listener, threshold, data)
		self.levelListeners.append(listener_info)

	def removeLevelListener(self, listener):
		self.levelListeners = filter(lambda x: x[0] != listener, self.levelListeners)

	def grow_daily_forever(self):
		while True:
			yield self.sim.env.timeout(24*60)
			#self.log(f"Level increase to {tons_to_string(self.level + self.daily_growth_rate)} / {tons_to_string(self.capacity)}  ({to_percentage_string((self.level + self.daily_growth_rate) / self.capacity)})")
			self.put(self.daily_growth_rate)


class Vehicle():	
	def log(self, message):
		self.sim.log(f"Vehicle #{self.index}: {message}")

	def warn(self, message):
		self.sim.warn(f"Vehicle #{self.index}: {message}")

	def __init__(self, sim, index, home_depot_index):
		self.sim = sim
		self.index = index
		self.home_depot_index = home_depot_index

		# Load and capacity
		self.load_capacity = sim.config['vehicle_template']['load_capacity']
		self.load_level = 0

		# Work shift
		self.max_route_duration = sim.config['vehicle_template']['max_route_duration']

		# Location and movement
		self.moving = False
		self.location_index = sim.depots[self.home_depot_index].location_index
		# TODO: routing

		self.log(self.get_location_string())

	def get_location_string(self):
		if self.moving == False:
			if self.location_index == self.sim.depots[self.home_depot_index].location_index:
				return f"Stationary at depot #{self.home_depot_index} (home depot)"
			else:
				return f"TODO: Stationary location other than home depot not implemented"
		return "TODO: En route location not implemented"

	def get_location_coordinates(self):
		if self.moving == False:
			return self.sim.location_coordinates[self.location_index]
		return (None, None) # TODO

	def put_load(value):
		self.load_level += value
		self.log(f"Load level increased to {tons_to_string(self.load_level)} / {tons_to_string(self.load_capacity)} ({to_percentage_string(self.load_level/self.load_capacity)})")
		if (self.load_level > self.capacity):
			self.warn("Overload")


# Depot class
class Depot():	
	def log(self, message):
		self.sim.log(f"Depot #{self.index}: {message}")

	def warn(self, message):
		self.sim.warn(f"Depot #{self.index}: {message}")

	def __init__(self, sim, index):
		self.sim = sim
		self.index = index
		self.location_index = sim.config['depots'][self.index]['location_index']


# Terminal class
class Terminal():
	def log(self, message):
		self.sim.log(f"Terminal #{self.index}: {message}")

	def warn(self, message):
		self.sim.warn(f"Terminal #{self.index}: {message}")

	def __init__(self, sim, index):
		self.sim = sim
		self.index = index
		self.location_index = sim.config['terminals'][self.index]['location_index']


class WastePickupSimulation():

	def log(self, message):
		print(f"{time_to_string(self.env.now)} - {message}")

	def warn(self, message):
		print(f"{time_to_string(self.env.now)} WARNING - {message}")	

	def __init__(self, config):		
		self.config = config

		# Create SimPy environment
		self.env = simpy.Environment()

		# Create pickup sites as objects
		self.pickup_sites = [PickupSite(self, i) for i in range(len(self.config['pickup_sites']))]

		# Create depots as objects
		self.depots = [Depot(self, i) for i in range(len(self.config['depots']))]

		# Create terminals as objects
		self.terminals = [Terminal(self, i) for i in range(len(self.config['terminals']))]

		# Create vehicles as objects
		self.vehicles = []
		for depot_index, depot in enumerate(self.config['depots']):
			for i in range(depot['num_vehicles']):
				self.vehicles.append(Vehicle(self, len(self.vehicles), depot_index))

		# Monitor pickup site levels
		for site in self.pickup_sites:
			site.addLevelListener(self.site_full, site.capacity, {"site": site})
		self.daily_monitoring_activity = self.env.process(self.daily_monitoring())
		
		# Daily vehicle routing
		self.daily_routing_activity = self.env.process(self.daily_routing())	

	def site_full(self, site):
		self.warn(f"Site #{site.index} is full.")

	def daily_monitoring(self):
		while True:
			self.log(f"Monitored levels: {', '.join(map(lambda x: to_percentage_string(x.level/x.capacity), self.pickup_sites))}")
			yield self.env.timeout(24*60)

	def daily_routing(self):
		while True:
			routing_input = {
				'pickup_sites': list(map(lambda pickup_site: {
					'capacity': pickup_site.capacity,
					'level': pickup_site.level,
					'growth_rate': pickup_site.daily_growth_rate/(24*60),
					'location_index': pickup_site.location_index
				}, self.pickup_sites)),
				'depots': list(map(lambda depot: {
					'location_index': depot.location_index
				}, self.depots)),
				'terminals': list(map(lambda terminal: {
					'location_index': terminal.location_index
				}, self.terminals)),
				'vehicles': list(map(lambda vehicle: {
					'load_capacity': vehicle.load_capacity,
					'home_depot_index': vehicle.home_depot_index,
					'max_route_duration': vehicle.max_route_duration,
				}, self.vehicles)),
				'distance_matrix': self.config['distance_matrix'],
				'duration_matrix': self.config['duration_matrix']
			}

			with open('routing_input.json', 'w') as outfile:
				json.dump(routing_input, outfile, indent=4)

			routing_output = heuristic_router(routing_input)
			# TODO: use the routes

			yield self.env.timeout(24*60)


	def sim_run(self):
		self.env.run(until=self.config["sim_runtime_days"]*24*60)
		self.log("Simulation finished")


def preprocess_sim_config(sim_config):

	# Create configurations for pickup sites using known data and random values	
	sim_config['pickup_sites'] = []
	with open(sim_config['pickup_sites_filename']) as pickup_sites_file:
		pickup_sites_geojson = json.load(pickup_sites_file)
	for pickup_site in pickup_sites_geojson['features']:
		pickup_site_config = {
			**pickup_site['properties'],
			'coordinates': tuple(pickup_site['geometry']['coordinates']),
			'capacity': random.randrange(1, 4)
		}
		pickup_site_config['daily_growth_rate'] = pickup_site_config['capacity']*np.random.lognormal(np.log(1 / ((14 + 21) / 2)), 0.1) # Log-normal dist of 2 to 3 weeks to be full.
		pickup_site_config['level'] = pickup_site_config['capacity']*np.random.uniform(0, 0.8)
		sim_config['pickup_sites'].append(pickup_site_config)

	# Create configurations for terminals using known data
	sim_config['terminals'] = []
	with open(sim_config['terminals_filename']) as terminals_file:
		terminals_geojson = json.load(terminals_file)
	for terminal in terminals_geojson['features']:
		terminal_config = {
			**terminal['properties'],
			'coordinates': tuple(terminal['geometry']['coordinates'])
		}
		sim_config['terminals'].append(terminal_config)
		
	# Create configurations for depots
	with open(sim_config['depots_filename']) as depots_file:
		depots_geojson = json.load(depots_file)
	for index, depot in enumerate(depots_geojson['features']):
		depot_config = {
			**depot['properties'],
			**sim_config['depots'][index],
			'coordinates': tuple(depot['geometry']['coordinates'])
		}
		sim_config['depots'][index] = depot_config

	# Collect coordinates of everything into a list of location coordinates. Store the location indexes
	def set_location_index_and_get_coordinates(x, location_index):
		x['location_index'] = location_index
		return x['coordinates']

	sim_config['location_coordinates'] = list(map(lambda x: set_location_index_and_get_coordinates(x[1], x[0]), enumerate([*sim_config['pickup_sites'], *sim_config['terminals'], *sim_config['depots']])))

	# Calculate geodesic distance matrix
	sim_config['distance_matrix'] = np.ndarray((len(sim_config['location_coordinates']), len(sim_config['location_coordinates'])), dtype=np.float32)
	sim_config['duration_matrix'] = np.ndarray((len(sim_config['location_coordinates']), len(sim_config['location_coordinates'])), dtype=np.float32)
	for b_index, b in enumerate(sim_config['location_coordinates']):
		for a_index, a in enumerate(sim_config['location_coordinates']):
			sim_config['distance_matrix'][b_index, a_index] = geodesic(a, b).m
			sim_config['duration_matrix'][b_index, a_index] = sim_config['distance_matrix'][b_index, a_index] / 1000 / 80 * 60 # 80 km/h
	sim_config['distance_matrix'] = sim_config['distance_matrix'].tolist()
	sim_config['duration_matrix'] = sim_config['duration_matrix'].tolist()

	print(55555555, sim_config['location_coordinates'])

	# Request distacne matrix
	matrix_json = request_distance_matrix(sim_config['location_coordinates'])
	print(len(sim_config['location_coordinates']))
	print(matrix_json.keys())
	sim_config['distance_matrix'] = matrix_json['distances'] 
	print(sim_config['distance_matrix'])
	# locations as a list of lists wit lat, long sim_config['location_coordinates']
	# pass it to API function 
	# store distacne matrix


	with open('sim_config.json', 'w') as outfile:
		json.dump(sim_config, outfile, indent=4)
