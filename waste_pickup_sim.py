import math
import time
import simpy
import random
import numpy as np
import queue as queue
import json
import functools
from geopy.distance import geodesic
from os.path import exists
from datetime import datetime
import os

from routing_api import get_distance_and_duration_matrix


def time_to_string(minutes):
	hours = math.floor(minutes/60)
	minutes -= hours*60
	days = math.floor(hours/24)
	hours -= days*24
	return f"{str(days):>3}d {str(hours).zfill(2)}:{str(math.floor(minutes)).zfill(2)}"

def tons_to_string(tons):
	return f"{tons:.3f}t"

def lonlat_to_string(lonlat):
	return f"({lonlat[0]:.5f}, {lonlat[1]:.5f})"

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

	# Heuristic router only routes one day at a time.
	routing_output = {
		'days': [{
			'vehicles': [{
				'route': route
			} for route in vehicle_routes]
		}]
	}
	
	#print(routing_output)

	return routing_output


# Any entity in the simulation that has an index which should be mentioned in logging. We don't have other kinds of entities.
class IndexedSimEntity():

	def log(self, message):
		self.sim.log(f"{type(self).__name__} #{self.index}: {message}")

	def warn(self, message):
		self.sim.warn(f"{type(self).__name__}e #{self.index}: {message}")

	def __init__(self, sim, index):
		self.sim = sim
		self.index = index

		# Statistics
		self.total_run_time = 0


# Any entity in the simulation that is indexed and also has a location index
class IndexedLocation(IndexedSimEntity):

	def __init__(self, sim, index, location_index):
		super().__init__(sim, index)
		self.location_index = location_index
		self.lonlat = sim.config['location_lonlats'][location_index]
		sim.locations[location_index] = self

# Pickup site
class PickupSite(IndexedLocation):

	def __init__(self, sim, index):

		super().__init__(sim, index, sim.config['pickup_sites'][index]['location_index'])

		self.capacity = sim.config['pickup_sites'][index]['capacity']
		self.level = sim.config['pickup_sites'][index]['level']
		self.levelListeners = []

		self.daily_growth_rate = sim.config['pickup_sites'][index]['daily_growth_rate']
		self.log(f"Initial level: {tons_to_string(self.level)} of {tons_to_string(self.capacity)} ({to_percentage_string(self.level / self.capacity)}), growth rate: {tons_to_string(self.daily_growth_rate)}/day")

		self.growth_process = sim.env.process(self.grow_daily_forever())

	# Put some amount into the containers at the site
	def put(self, amount):
		listeners_to_message_maybe = list(filter(lambda x: self.level < x[1], self.levelListeners))
		self.level += amount
		listeners_to_message = list(filter(lambda x: self.level >= x[1], listeners_to_message_maybe))
		if len(listeners_to_message):
			self.log(f"Level increase past threshold for {len(listeners_to_message)} listeners.")
		for x in listeners_to_message:
			x[0](**x[2])

	# Get some amount from the containers at the site
	def get(self, amount):
		self.level -= amount

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


# Vehicle
class Vehicle(IndexedSimEntity):	

	def __init__(self, sim, index, home_depot_index):
		super().__init__(sim, index)
		self.home_depot_index = home_depot_index

		# Load level and capacity
		self.load_capacity = sim.config['vehicle_template']['load_capacity']
		self.load_level = 0

		# Work shift
		self.max_route_duration = sim.config['vehicle_template']['max_route_duration']

		# Pickup duration
		self.pickup_duration = sim.config['vehicle_template']['pickup_duration']

		# Location and movement
		self.moving = False
		self.location_index = sim.depots[self.home_depot_index].location_index
		self.vehicle_odometer = 0	

		self.log(f"At {type(sim.locations[self.location_index]).__name__} #{sim.locations[self.location_index].index}")


	# Get current location
	def get_lonlat(self):
		if self.moving == False:
			return self.sim.locations[self.location_index].lonlat
		else:
			# Interpolate between current source and destination locations
			route_step_fractional_progress = (self.sim.env.now - self.route_step_departure_time) / self.sim.duration_matrix[self.route[self.route_step]][self.route[self.route_step + 1]]
			if (route_step_fractional_progress > 1): 
				route_step_fractional_progress = 1 # After travel there may be time spent working at pickup site
			source_location_lonlats = self.sim.locations[self.route[self.route_step]].lonlat
			destination_location_lonlats = self.sim.locations[self.route[self.route_step + 1]].lonlat
			return (
				source_location_lonlats[0] + route_step_fractional_progress*(destination_location_lonlats[0] - source_location_lonlats[0]),
				source_location_lonlats[1] + route_step_fractional_progress*(destination_location_lonlats[1] - source_location_lonlats[1])
			)

	def put_load(self, value):
		self.load_level += value
		self.log(f"Load level increased to {tons_to_string(self.load_level)} / {tons_to_string(self.load_capacity)} ({to_percentage_string(self.load_level/self.load_capacity)})")
		if (self.load_level > self.capacity):
			self.warn("Overload")

	# Assign route for vehicle
	def assign_route(self, route):
		self.route_activity = self.sim.env.process(self.run_assign_route(route))

	def run_assign_route(self, route):
		if len(route) > 0:
			self.moving = True
			moving_start_time = self.sim.env.now
			self.route = route
			for self.route_step in range(len(route) - 1):
				self.route_step_departure_time = self.sim.env.now
				depart_location = self.sim.locations[self.route[self.route_step]]
				arrive_location = self.sim.locations[self.route[self.route_step + 1]]
				self.log(f"Depart from {type(depart_location).__name__} #{depart_location.index}")
				yield self.sim.env.timeout(self.sim.duration_matrix[self.route[self.route_step]][self.route[self.route_step + 1]])
				self.record_distance_travelled(self.sim.distance_matrix[self.route[self.route_step]][self.route[self.route_step + 1]])
				self.log(f"Arrive at {type(arrive_location).__name__} #{arrive_location.index}")

				if isinstance(arrive_location, PickupSite):
					# Arrived at a pickup site
					pickup_site = arrive_location
					if pickup_site.level > 0:
						if self.load_level + pickup_site.level > self.load_capacity: 
							# Can only take some
							get_amount = self.load_capacity - self.load_level
							pickup_site.get(get_amount)
							self.load_level = self.load_capacity
							yield self.sim.env.timeout(self.pickup_duration)
						else:
							# Can take all
							get_amount = pickup_site.level
							self.load_level += get_amount
							pickup_site.get(get_amount)
							yield self.sim.env.timeout(self.pickup_duration)
						self.log(f"Pick up {tons_to_string(get_amount)} from pickup site #{pickup_site.index} with {tons_to_string(pickup_site.level)} remaining. Vehicle load {tons_to_string(self.load_level)} / {tons_to_string(self.load_capacity)}")
					else:
						self.log(f"Nothing to pick up at pickup site #{pickup_site.index}")			

				elif isinstance(arrive_location, Depot):
					# Arrived at a depot
					depot = arrive_location
					self.log(f"Dumped the load {tons_to_string(self.load_level)} at depot #{depot.index}")
					self.load_level = 0

			# Mark as not moving at final destination
			self.moving = False
			moving_end_time = self.sim.env.now
			self.total_run_time += moving_end_time - moving_start_time
			self.location_index = route[-1]



	def record_distance_travelled(self, distance_driven):
		"""
		Remove later?
		"""
		self.vehicle_odometer =+ distance_driven


# Depot where the vehicles start from in the beginning of the day and go to at the end of the day
class Depot(IndexedLocation):

	def __init__(self, sim, index):
		super().__init__(sim, index, sim.config['depots'][index]['location_index'])


# Terminal where waste is brought to at the end of the day, before returning to depot
class Terminal(IndexedLocation):

	def __init__(self, sim, index):
		super().__init__(sim, index, sim.config['terminals'][index]['location_index'])


# Simulation
class WastePickupSimulation():

	def log(self, message):
		log_message = f'{time_to_string(self.env.now)} - {message}'
		print(log_message)
		# Add to csv log for later vis
		self.action_log.append(log_message)		

	def warn(self, message):
		warn_message = f"{time_to_string(self.env.now)} WARNING - {message}"
		print(warn_message)	
		# Add to csv log for later vis
		self.action_log.append(warn_message)
		self.sim_records['warnings'].append(warn_message) 

	def __init__(self, config):		
		self.config = config
		self.run_start = f"{datetime.now()}".replace(':', '-')

		# Create SimPy environment
		self.env = simpy.Environment()

		# For gathering statistics
		self.action_log = []
		self.sim_records = {'warnings' : []}

		# Distance and duration matrixes
		self.distance_matrix = config['distance_matrix']
		self.duration_matrix = config['duration_matrix']

		# Create a list of locations so that we can easily check the type of a location. These will be populated by any IndexedLocation
		self.locations = [None for _ in config['location_lonlats']]

		# Create pickup sites as objects
		self.pickup_sites = [PickupSite(self, i) for i in range(len(config['pickup_sites']))]

		# Create depots as objects
		self.depots = [Depot(self, i) for i in range(len(config['depots']))]

		# Create terminals as objects
		self.terminals = [Terminal(self, i) for i in range(len(config['terminals']))]

		# Create vehicles as objects
		self.vehicles = []
		for depot_index, depot in enumerate(config['depots']):
			for i in range(depot['num_vehicles']):
				self.vehicles.append(Vehicle(self, len(self.vehicles), depot_index))

		# Monitor pickup site levels
		for site in self.pickup_sites:
			site.addLevelListener(self.site_full, site.capacity, {"site": site})
		self.daily_monitoring_activity = self.env.process(self.daily_monitoring())
		
		# Daily vehicle routing
		self.routing_output = None # No routes planned yet. The value None will cause them to be planned
		self.daily_routing_activity = self.env.process(self.daily_routing())	

		# Hourly vehicle tracking (Could be at higher rate)
		self.vehicle_tracking_activity = self.env.process(self.vehicle_tracking())

		# Route logs
		self.route_logs = [[] for _ in self.vehicles]

	def site_full(self, site):
		self.warn(f"Site #{site.index} is full.")

	def vehicle_tracking(self):
		while True:
			#self.log(f"Vehicle locations: {', '.join(map(lambda x: lonlat_to_string(x.get_lonlat()), self.vehicles))}")
			for vehicle in self.vehicles:
				if vehicle.moving:
					self.route_logs[vehicle.index].append((self.env.now, vehicle.get_lonlat()))
			yield self.env.timeout(0.25)

	def daily_monitoring(self):
		while True:
			self.log(f"Monitored levels: {', '.join(map(lambda x: to_percentage_string(x.level/x.capacity), self.pickup_sites))}")
			yield self.env.timeout(24*60)

	def daily_routing(self):
		while True:
			# Request routing when not currently available
			if self.routing_output == None or len(self.routing_output['days']) == 0:
				# Input to routing optimizer
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

				filename = 'temp/routing_input.json'
				os.makedirs(os.path.dirname(filename), exist_ok=True)
				with open(filename, 'w') as outfile:
					json.dump(routing_input, outfile, indent=4)

				# Comment/uncomment: heuristic router
				#self.routing_output = heuristic_router(routing_input)

				# Comment/uncomment: genetic algorithm router
				filename = 'log/routing_optimizer_log.txt'
				os.makedirs(os.path.dirname(filename), exist_ok=True)
				os.system(f"routing_optimizer>{filename}")
				with open('temp/routing_output.json') as infile:
					self.routing_output = json.load(infile)

			# Assign routes
			for vehicle_index, vehicle_routing_output in enumerate(self.routing_output['days'][0]['vehicles']):
				self.vehicles[vehicle_index].assign_route(vehicle_routing_output['route'])

			# We have used the first day of multiple days of routing output. Remove that day from the routing output
			self.routing_output['days'] = self.routing_output['days'][1:]

			# Wait 24h until next route optimization
			yield self.env.timeout(24*60)


	def sim_run(self):
		start_time = time.time()
		self.env.run(until=self.config["sim_runtime_days"]*24*60)
		end_time = time.time()
		self.total_time = end_time-start_time # Excuding config preprocessing
		self.log(f"Simulation finished with {self.total_time}s of computing")
		filename = f"log/routes_log_{self.run_start}.json"
		os.makedirs(os.path.dirname(filename), exist_ok=True)
		with open(filename, 'w') as f:
			print("x,y,t", file=f)
			for vehicle_log in self.route_logs:
				for stop in vehicle_log:
					print(f"{stop[1][0]},{stop[1][1]},{stop[0]}", file=f)


	def save_log(self):
		"""
		TODO: Log processor somwhere else
		"""
		# Get log from saved Save log as csv file
		json_log = json.dumps(self.action_log)
		filename = f"log/sim_log_{self.run_start}.json"
		# TODO! select folder structure for saving data
		os.makedirs(os.path.dirname(filename), exist_ok=True)
		with open(f'{filename}', 'w') as f:
			json.dump(json_log, f, indent=4)


	def sim_record(self):
		"""
		"""
		# Create a dict (record_[time.now.to_string]that records
		self.sim_records['computational_time'] = self.total_time # comptutational time
		self.sim_records['vehicles_driving_stats'] = [{'index':v.index, 'runtime':v.total_run_time, 'distance':v.vehicle_odometer} for v in self.vehicles] # time of vehicles driving
		#self.sim_records['vehicles_distance'] = [[v.index, v.vehicle_odometer] for v in self.vehicles] # time of vehicles driving
		# vechicle driving distance
		# level listeners alerts # are added in warnings level
		filename = f"log/sim_record_{self.run_start}.json"

		os.makedirs(os.path.dirname(filename), exist_ok=True)
		with open(f'{filename}', 'w') as f:
			json.dump(self.sim_records, f, indent=4)

		print(f"Simulaton record saved to {filename}")


def preprocess_sim_config(sim_config, sim_config_filename):

	# Create configurations for pickup sites using known data and random values	
	sim_config['pickup_sites'] = []
	with open(sim_config['pickup_sites_filename']) as pickup_sites_file:
		pickup_sites_geojson = json.load(pickup_sites_file)
	for pickup_site in pickup_sites_geojson['features']:
		pickup_site_config = {
			**pickup_site['properties'],
			'lonlats': tuple(pickup_site['geometry']['coordinates']),
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
			'lonlats': tuple(terminal['geometry']['coordinates'])
		}
		sim_config['terminals'].append(terminal_config)
		
	# Create configurations for depots
	with open(sim_config['depots_filename']) as depots_file:
		depots_geojson = json.load(depots_file)
	for index, depot in enumerate(depots_geojson['features']):
		depot_config = {
			**depot['properties'],
			**sim_config['depots'][index],
			'lonlats': tuple(depot['geometry']['coordinates'])
		}
		sim_config['depots'][index] = depot_config

	# Collect lonlats of everything into a list of location lonlats. Store the location indexes
	def set_location_index_and_get_lonlats(x, location_index):
		x['location_index'] = location_index
		return x['lonlats']

	sim_config['location_lonlats'] = list(map(lambda x: set_location_index_and_get_lonlats(x[1], x[0]), enumerate([*sim_config['pickup_sites'], *sim_config['terminals'], *sim_config['depots']])))

	# Load previous sim config
	try:
		with open(sim_config_filename) as cached_sim_config_file:
			cached_sim_config = json.load(cached_sim_config_file)
	except:
		cached_sim_config = None

	# Use previous distance and duration matrixes if the locations match within 0.001 deg of absolute error
	if cached_sim_config != None and np.sum(np.absolute(np.array(cached_sim_config['location_lonlats']) - np.array(sim_config['location_lonlats']))) < 0.001:
		sim_config['distance_matrix'] = cached_sim_config['distance_matrix']
		sim_config['duration_matrix'] = cached_sim_config['duration_matrix']
	else:
		# Calculate geodesic distance and duration matrixes
		#geodesic_distance_matrix = np.ndarray((len(sim_config['location_lonlats']), len(sim_config['location_lonlats'])), dtype=np.float32)
		#geodesic_duration_matrix = np.ndarray((len(sim_config['location_lonlats']), len(sim_config['location_lonlats'])), dtype=np.float32)
		#for b_index, b in enumerate(sim_config['location_lonlats']):
			#for a_index, a in enumerate(sim_config['location_lonlats']):
				#geodesic_distance_matrix[b_index, a_index] = geodesic((a[1], a[0]), (b[1], b[0])).m  #geodesic() uses latlon
				#geodesic_duration_matrix[b_index, a_index] = geodesic_distance_matrix[b_index, a_index] / 1000 / 60 * 60 # / 1000m/km / 60km/h / 60min/h
		#sim_config['geodesic_distance_matrix'] = geodesic_distance_matrix.tolist()
		#sim_config['geodesic_duration_matrix'] = geodesic_duration_matrix.tolist()

		# Get routing API based distance and duration matrixes
		distance_and_duration_matrixes = get_distance_and_duration_matrix(sim_config['location_lonlats'])
		sim_config['distance_matrix'] = distance_and_duration_matrixes["distance_matrix"].tolist()
		sim_config['duration_matrix'] = distance_and_duration_matrixes["duration_matrix"].tolist()

	os.makedirs(os.path.dirname(sim_config_filename), exist_ok=True)
	with open(sim_config_filename, 'w') as outfile:
		json.dump(sim_config, outfile, indent=4)
