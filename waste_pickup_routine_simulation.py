import math
import simpy
import random
import numpy as np


grey_containers_config ={
	"capacity_range" : [10, 20], # tonnes
	"initial_load_range" :[0, 0.95], # %
	'initial_requested_range' : [0, 6], # days old initially 1 day is added to range is like this
}

vehicles_config = {
	'load_capacity' : 18, # Tonnes
	#### Add all service level agreement related config here later
	'max_shift_duration' : 540, # Minutes 
	'break_duration' : 45, # Minutes # Break Happens after 1/2 of drivetime 
	'allow_break' : 1,
	'grey_site_pickup_duration' : 15 # Minutes
}

city_config = {
	'name' : 'Turku',

	'drivetime_range' : [5, 60], # Minutes
	'num_grey_pickup_sites' : 100, # N

	'num_grey_vehicles' : 3, # N

	'num_blue_pickup_sites' : 0, # N
	#'vehicles_config' : vehicles_config
}

sim_config = {
	#'runtime' : 7*24*60,  # Week *day*hours*minutes Minutes
	'runtime_days' : 7,
	'P_VALUE' : 0.8, # % Of container to be reported # For automated system # Minimum allowed to be picked up
	'T_VALUE' : 30 # Time to go off route to pick up an extra contianer nearby
	# 'grey_site_requested_range' : [0, 7], also optimizing # later
}


def time_to_string(minutes):
	hours = math.floor(minutes/60)
	minutes -= hours*60
	days = math.floor(hours/24)
	hours -= days*24
	return f"{str(days):>3}d {str(hours).zfill(2)}:{str(minutes).zfill(2)}"


def tons_to_string(tons):
	return f"{tons:.3f} tons"


def log(env, message):
	print(f"{time_to_string(env.now)} - {message}")


class GreyPickUpSite(simpy.Container):
	"""
	Inherits from simpy.Container class.
	"""
	def __init__(self, env, city, index, grey_containers_config):
		"""
		Creating simpy.COntainer objects with additional parameters of index, request age and growth rate in this contianer 
		"""
		capacity = random.randint(*grey_containers_config['capacity_range'])
		initial_requested_range = grey_containers_config['initial_requested_range']

		super().__init__(env, capacity)
		self.env = env
		self.city = city

		self.index = index
		self.grey_site_initial_load_range = grey_containers_config['initial_load_range']
		
		self.put(capacity*random.uniform(*self.grey_site_initial_load_range))
		if self.level / self.capacity >= sim_config['P_VALUE']:
			self.request = random.randint(*initial_requested_range)
			self.city.full_grey_sites.append(self)
		else:
			self.request = 0 #) when not requested, request starts from 1
		log(env, f"On waste site #{index} there are initially {tons_to_string(self.level)} / {tons_to_string(self.capacity)} [{self.level / self.capacity * 100}%]")

		self.daily_growth_rate = float(np.random.normal((14 + 21) / 2, 1, 1) / capacity) # Normal dist of 2 to 3 weeks to be full. Fix for more configurable later

		self.action = env.process(self.grow())
		self.action = env.process(self.request_pickup())




	def grow(self):		
		while True:
			yield self.env.timeout(24*60)
			self.put(self.daily_growth_rate)
			log(self.env, f"Grey container {self.index} level got increased by ({self.daily_growth_rate})to {tons_to_string(self.level)} / {tons_to_string(self.capacity)}  [{self.level / self.capacity * 100}%]")


	def request_pickup(self):
		while True:
			if self.level / self.capacity >= sim_config['P_VALUE']: # Update for better configability
				self.request += 1
				self.city.full_grey_sites.append(self) if self not in self.city.full_grey_sites else self.city.full_grey_sites # I love this line <3
				log(self.env, f"Grey container {self.index} requests a pick up! Request was made {self.request} days ago!") # {self.request - 1} for more logical readability
				yield self.env.timeout(24*60)
			else:
				self.request = 0
				if self in self.city.full_grey_sites: self.city.full_grey_sites.remove(self)
				yield self.env.timeout(24*60)



class OperatingVehicle(simpy.Container):
	"""
	Inherits from simpy.Container class.
	"""

	def __init__(self, env, city, index, vehicles_config):

		self.env = env  # Simpy env
		self.index = index # Index of vehicle

		self.route = [] # Scheduled route for a day
		self.city = city # City object

		self.worktime = vehicles_config['grey_site_pickup_duration']

		self.max_shift_duration = vehicles_config['max_shift_duration']
		self.break_duration = vehicles_config['break_duration']
		self.allow_break = vehicles_config['allow_break']

		self.shift_start_time = None # Daily shift start time
		self.vehicle_current_runtime = 0 # Runtime for a day
		self.time_to_complete_next_task = 0

		self.current_destinaiton = None # Current site to move to
		self.current_location = 0 # Depot

		super().__init__(env, capacity=vehicles_config['load_capacity'])
		log(env, f"Truck {self.index} is introduced to the city")


	def lunch_break(self):
		"""
		If there are any lunch breaks left for the today's shift. If so stops vehicle for a break
		"""
		log(self.env, "Check up on break time")
		if self.vehicle_current_runtime >= self.max_shift_duration / 2:
			log(self.env, f"Vehicle {self.index} stops on a lunch_break")
			self.allow_break = 0
			yield self.env.timeout(self.break_duration)


	def approximate_next_task(self):
		"""
		Check the time it will take tro complete next tasks based on drivetime there and loading time
		"""
		#distance matrix + worktime

		self.time_to_complete_next_task = self.city.distance_matrix[self.current_location][self.current_destinaiton.index] + self.worktime * 2


	def end_shift(self):
		"""Function that will make vehicle go to depot and reset daily parameters"""
		#curr runtime + next task approx >= maxruntime
		#
		#log(self.env, f"Shift for truck {self.index} over with runtime of {time_to_string(self.vehicle_current_runtime)}")
		#log(env, 333333, math.ceil(self.env.now / 1440) * 1440)
		#to_timeout = 
		#log(env, to_timeout)
		log(self.env, f"Shift for vehicle {self.index} over with runtime of {time_to_string(self.vehicle_current_runtime)}")

		yield self.env.timeout(0)
		#yield self.env.timeout(math.ceil(self.env.now / 1440) * 1440 - self.env.now)
		

	def statistics(self):
		"""Collect curr drive time for a day"""
		# driving time
		# curr runtime = env.now - shift start time
		# other working time  #later
		current_runtime = self.env.now - self.shift_start_time
		self.vehicle_current_runtime = current_runtime
		log(self.env, f"Vehicle {self.index} current runtime updated! ({self.vehicle_current_runtime})")


	def drop_load(self):
		"""
		Drop load on the depot and empty Container
		"""
		
		yield self.env.timeout(self.city.distance_matrix[self.current_destinaiton.index][0]) # Drive to base
		log(self.env, f"Truck {self.index} arrives to DEPOT")
		self.current_location = 0
		yield self.env.timeout(5) #Drop off time
		log(self.env, f"Truck {self.index} drops {tons_to_string(self.level)} on DEPOT")
		self.get(self.level)



	def pick_up_load(self):
		"""
		Picking up of container routine
		"""
		
		yield self.env.timeout(self.city.distance_matrix[0][self.current_destinaiton.index]) # Drive time here
		log(self.env, f"Truck {self.index} arrives to {self.current_destinaiton.index}")
		self.current_location = self.current_destinaiton.index
		yield self.env.timeout(self.worktime) # Picking up time


		if self.current_destinaiton.level >= (self.capacity - self.level):
			to_pick_up = (self.capacity - self.level)
		else:
			to_pick_up = self.current_destinaiton.level
	

		if to_pick_up != 0:
			self.current_destinaiton.get(to_pick_up)
			self.put(to_pick_up)
		else:
			log(self.env, f"Empty container at {self.current_destinaiton.index}")
	
		log(self.env, f"Truck {self.index} picks up {tons_to_string(to_pick_up)} on {self.current_location}")
		log(self.env, f"{tons_to_string(self.current_destinaiton.level)} left on gray site {self.current_location}")
	

		log(self.env, f"Truck {self.index} now has {tons_to_string(self.level)}")
		if self.level == self.capacity:
				log(self.env, f"Truck {self.index} enroute to DEPOT")
				yield self.env.process(self.drop_load())


	def start_shift(self):
		"""
		Simulate given route for vehicle
		"""
		# for site in route
		self.shift_start_time = self.env.now
		log(self.env, f"Vehicle {self.index} has started it's shift")
		
		self.vehicle_current_runtime = 0
		for site in self.route:

			#log(env, site.level)
			self.statistics()
			self.current_destinaiton = site
			self.approximate_next_task()

			if self.vehicle_current_runtime + self.time_to_complete_next_task > self.max_shift_duration:
				

				yield self.env.process(self.end_shift())
				#self.route = [0]
			else:
				# Approximate next tasks
				# if over allowed runtime end shift
				log(self.env, f"Vehicle {self.index} is heading towards site {self.current_destinaiton.index}")
				yield self.env.process(self.pick_up_load())
				
				if self.allow_break:
					yield self.env.process(self.lunch_break())

		log(self.env, f"Shift for vehicle {self.index} over with runtime of {time_to_string(self.vehicle_current_runtime)}")
		yield self.env.process(self.end_shift())


class City:
	def __init__(self, env, city_config):

		self.name = city_config['name'] # Name of city to simulate arbitraryx
		self.env = env
		self.P_VALUE = city_config['P_VALUE'] # Got from sim config

		self.num_grey_vehicles = city_config['num_grey_vehicles']
		self.operating_vehicles = []

		self.num_grey_pickup_sites = city_config['num_grey_pickup_sites'] # Initialaize total number of grey containers

		self.grey_sites = [] # Initial empty list
		self.full_grey_sites = [] #Based on P value

		self.num_blue_pickup_sites = city_config['num_blue_pickup_sites'] # Initialaize total number of blue containers

		#self.max_shift_duration = city_config['vehicles_config']['max_shift_duration'] # Max runitime of the shift
		self.drivetime_range = city_config['drivetime_range']


		print(f"City '{self.name}' drafted with total of {self.num_grey_pickup_sites + self.num_blue_pickup_sites} [{self.num_grey_pickup_sites}|{self.num_blue_pickup_sites}] waste pick up sites with 1 depot. @{self.env}")
		self.create_vehicles()
		self.create_random_distance_matrix(verbose=False)
		self.create_waste_pick_up_sites()

		self.action = env.process(self.monitor_requests())
		

	def create_waste_pick_up_sites(self):
		"""
		Creating containers with config
		"""
		log(self.env, f"Creating {self.num_grey_pickup_sites} containers")
		for i in range(self.num_grey_pickup_sites):
			self.grey_sites.append(GreyPickUpSite(self.env, self, i + 1, grey_containers_config)) # i + 1 since 0 is depot


	def monitor_requests(self):
		"""Read requests of the sites daily"""
		while True:
			self.full_grey_sites = sorted(self.full_grey_sites, key=lambda x: x.request, reverse=True)
			log(self.env, f"There are currently {len(self.full_grey_sites)} full grey sites ready, with {self.num_grey_vehicles} vehicles ready for work.")
			yield self.env.timeout(24*60)



	def create_vehicles(self):
		"""
		Initializing vehicles
		"""
		for i in range(self.num_grey_vehicles):
			self.operating_vehicles.append(OperatingVehicle(self.env, self, i, vehicles_config))


	def assign_grey_sites(self):
		"""
		Distribute containers to existing trucks NOT PROUD OF THIS FUNCTION
		"""
		to_assign = [i.index for i in self.full_grey_sites]
		routes = [[] for _ in range(self.num_grey_vehicles)]

		for _ in range(len(to_assign) // len(routes)):
			for r in routes:
				r.append(to_assign[0])
				to_assign.remove(to_assign[0])
		
		for i in range(len(to_assign)):
			routes[i].append(to_assign[i])

		for i, operating_vehicle in enumerate(self.operating_vehicles):
			route = [self.grey_sites[s-1] for s in routes[i]] # Not sure how this works # Danger!
			operating_vehicle.route = route

			log(self.env, f"For vehicle {operating_vehicle.index} route {[s.index for s in operating_vehicle.route]} is assigned.")
		

	# Create init distance matrix        
	def create_random_distance_matrix(self, symmetrical=True, verbose=False):
		"""
		Imitation of driving time between wste sites
		"""
		num_locations = self.num_grey_pickup_sites + 1 # Plus depot
		min = self.drivetime_range[0]
		max = self.drivetime_range[1]

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
		
		if verbose:
			for i in distance_matrix:
				print(i)
		
		self.distance_matrix = distance_matrix


	def start_daily_shift(self):
		"""
		Daily shift starting
		"""
		while True:
			for vehicle in self.operating_vehicles:

				self.assign_grey_sites()
				self.env.process(vehicle.start_shift())
			yield self.env.timeout(24*60)

		#yield self.env.timeout(math.ceil(self.env.now / 1440) * 1440 - self.env.now)


class Simulation:

	def __init__(self, sim_config):

		self.env = simpy.Environment()

		self.runtime = sim_config['runtime_days'] * 24 * 60 # Minutes from days
		self.runtime_days = sim_config['runtime_days']

		self.action = self.env.process(self.run())

		self.env.run(until=self.runtime)


	def run(self):
		
		city_config['P_VALUE'] = sim_config['P_VALUE']

		self.city = City(self.env, city_config)
		

		yield self.env.process(self.city.start_daily_shift())

		log(env, env.now)




## Tessting field
sim = Simulation(sim_config)

