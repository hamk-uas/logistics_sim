import math
import simpy
import random
import numpy as np




vehicles_config = {
	'vehicle_load_capacity' : 18, # Tonnes
	#### Add all service level agreement related config here later
	'vehicle_max_runtime' : 540, # Minutes 
	'vehicle_break_time' : 45, # Minutes # Break Happens after 1/2 of drivetime 
	'lunch_breakes_allowed' : 1,
	 #TODO!!!!!!!!!!
	 #'vehicle_daily_rest' : 660 # Minutes
	 #'vehicle_weekly_limit' : 3360 # Minutes #Remove larter
	 # Two week working limit?
	 'grey_site_worktime' : 15 # Minutes

}

city_config = {
	'name' : 'Turku',

	'drivetime_range' : [5, 60], # Minutes
	'loading_time' : 5, # Minutes
	'num_grey_pickup_sites' : 100, # N
	'grey_site_capacity_range' : [10, 20], # tonnes
	'grey_site_initial_load_range' : [0, 0.95], # %
	'grey_site_requested_range' : [0, 7], # days old

	'num_grey_vehicles' : 3, # N

	'num_blue_pickup_sites' : 0, # N
	'vehicles_config' : vehicles_config
}

sim_config = {
	#'runtime' : 7*24*60,  # Week *day*hours*minutes Minutes
	'runtime_days' : 7,
	'P_VALUE' : 0.5, # % Of container to be reported # For automated system # Minimum allowed to be picked up
	'T_VALUE' : 30 # Time to go off route to pick up an extra contianer nearby
	# 'grey_site_requested_range' : [0, 7], also optimizing # later
}



class GreyPickUpSite(simpy.Container):
	"""
	Inherits from simpy.Container class.
	"""
	def __init__(self, env, index, request, capacity, initial_load):
		"""
		Creating simpy.COntainer objects with additional parameters of index, request age and growth rate in this contianer 
		"""
		super().__init__(env, capacity)
		self.index = index
		self.request = request # Alarm trigerred days ago
		self.put(initial_load)
		print(f"On waste site #{index} there are initially {self.level} tons at {env.now}")

		#
		self.daily_growth_rate = float(np.random.normal((14 + 21) / 2, 1, 1) / capacity) # Normal dist of 2 to 3 weeks to be full. Fix for more configurable later





class OperatingVehicle(simpy.Container):
	"""
	Inherits from simpy.Container class.
	"""

	def __init__(self, env, city, index, vehicles_config):

		self.env = env  # Simpy env
		self.index = index # Index of vehicle

		self.route = [] # Scheduled route for a day
		self.city = city # City object

		self.vehicle_max_runtime = vehicles_config['vehicle_max_runtime']
		self.vehicle_break_time = vehicles_config['vehicle_break_time']
		self.lunch_breakes_allowed = vehicles_config['lunch_breakes_allowed']

		self.shift_start_time = None # Daily shift start time
		self.vehicle_current_runtime = 0 # Runtime for a day
		self.time_to_complete_next_task = 0

		self.current_destinaiton = None # Current site to move to
		self.current_location = 0 # Depot

		super().__init__(env, capacity=vehicles_config['vehicle_load_capacity'])
		print(f"Truck {self.index} is available for a shift")


	#Add function for a schedulded break quickly later
	def lunch_break(self):
		"""
		If there are any lunch breaks left for the today's shift. If so stops vehicle for a break
		"""
		print("Check up on break time")
		if self.vehicle_current_runtime >= self.vehicle_max_runtime / 2:
			print(f"Vehicle {self.index} stops on a lunch_break at {self.env.now}")
			self.lunch_breakes_allowed = 0
			yield self.env.timeout(self.vehicle_break_time)


	def approximate_next_task(self):#TODO!!!!!!!!!!
		"""
		Check the time it will take tro complete next tasks based on drivetime there and loading time
		"""
		#distance matrix + worktime

		self.time_to_complete_next_task = self.city.distance_matrix[self.current_location][self.current_destinaiton.index] + self.city.loading_time * 2



	def end_shift(self):#TODO!!!!!!!!!!#TODO!!!!!!!!!!
		"""Function that will make vehicle go to depot and reset daily parameters"""
		#curr runtime + next task approx >= maxruntime
		#
		print(f"Shift for truck {self.index} over at {self.env.now} with runtime of {self.vehicle_current_runtime}")
		#print(333333, math.ceil(self.env.now / 1440) * 1440)
		#to_timeout = 
		#print(to_timeout)

		yield self.env.timeout(math.ceil(self.env.now / 1440) * 1440 - self.env.now)
		


	def statistics(self):
		"""Collect curr drive time for a day"""
		# driving time
		# curr runtime = env.now - shift start time
		# other working time  #later
		current_runtime = self.env.now - self.shift_start_time
		self.vehicle_current_runtime = current_runtime
		print(f"Vehicle {self.index} current runtime updated! Now is {self.vehicle_current_runtime}")



	def drop_load(self):
		"""
		Drop load on the depot and empty Container
		"""
		
		yield self.env.timeout(self.city.distance_matrix[self.current_destinaiton.index][0]) # Drive to base
		print(f"Truck {self.index} arrives to DEPOT at {self.env.now}")
		self.current_location = 0
		yield self.env.timeout(5) #Drop off time
		print(f"Truck {self.index} drops {self.level} tonns on DEPOT at {self.env.now}")
		self.get(self.level)


	def pick_up_load(self):
		"""
		Picking up of container routine
		"""
		
		#print("Picking up load ..../....\\..")
		#print(type(self.city.distance_matrix[0]))
		#print(self.city.distance_matrix[0][self.current_destinaiton.index])
		yield self.env.timeout(self.city.distance_matrix[0][self.current_destinaiton.index]) # Drive time here
		print(f"Truck {self.index} arrives to {self.current_destinaiton.index} at {self.env.now}")
		self.current_location = self.current_destinaiton.index
		yield self.env.timeout(self.city.loading_time) # Picking up time
		available_space = self.capacity - self.level
		#print(available_space)
		#print(type(self.current_destinaiton))
		if self.current_destinaiton.level >= available_space:
			to_pick_up = available_space
		else:
			to_pick_up = self.current_destinaiton.level
	

		if to_pick_up:
			self.current_destinaiton.get(to_pick_up)
			self.put(to_pick_up)
		else:
			print(f"Empty container at {self.current_destinaiton.index}")
	
		print(f"Truck {self.index} picks up {to_pick_up} tonns on {self.current_destinaiton.index} at {self.env.now}")
		print(f"{self.current_destinaiton.level} tonns left on gray site {self.current_destinaiton.index}")
	
		#load['current_load'] += to_pick_up
		print(f"Truck {self.index} now has {self.level} tonns at {self.env.now}")
		if self.level == self.capacity:
				print(f"Truck {self.index} enroute to DEPOT at {self.env.now}")
				yield self.env.process(self.drop_load())


	





	def simulate_route(self):
		"""
		Simulate given route for vehicle
		"""
		# for site in route
		print(f"Truck {self.index} has started it's shift at {self.env.now}")
		self.shift_start_time = self.env.now
		self.vehicle_current_runtime = 0
		for site in self.route:

			#print(site.level)
			self.statistics()
			self.current_destinaiton = site
			self.approximate_next_task()

			if self.vehicle_current_runtime > self.vehicle_max_runtime:

				yield self.env.process(self.end_shift())
			else:
				# Approximate next tasks
				# if over allowed runtime end shift
				print(f"Truck {self.index} is heading towards site {self.current_destinaiton.index} at {self.env.now}")
				#print(self.pick_up_load())
				yield self.env.process(self.pick_up_load())
				
				#self.approximate_next_task()
				if self.lunch_breakes_allowed:
					yield self.env.process(self.lunch_break())


	


# City
class City:
	def __init__(self, city_config):

		self.name = city_config['name'] # Name of city to simulate arbitraryx
		self.env = city_config['env']
		self.P_VALUE = city_config['P_VALUE'] # Got from sim config

		self.num_grey_vehicles = city_config['num_grey_vehicles']
		self.operating_vehicles = []

		self.num_grey_pickup_sites = city_config['num_grey_pickup_sites'] # Initialaize total number of grey containers
		self.grey_site_capacity_range = city_config['grey_site_capacity_range']
		self.grey_site_initial_load_range = city_config['grey_site_initial_load_range']
		self.grey_site_requested_range = city_config['grey_site_requested_range']
		self.grey_pick_sites = [] # Initial empty list
		self.full_grey_sites = [] #Based on P value

		self.num_blue_pickup_sites = city_config['num_blue_pickup_sites'] # Initialaize total number of blue containers

		self.vehicle_max_runtime = city_config['vehicles_config']['vehicle_max_runtime'] # Max runitime of the shift
		self.drivetime_range = city_config['drivetime_range']
		self.loading_time = city_config['loading_time']

		print(f"City '{self.name}' drafted with total of {self.num_grey_pickup_sites + self.num_blue_pickup_sites} [{self.num_grey_pickup_sites}|{self.num_blue_pickup_sites}] waste pick up sites. @{self.env}")


	def create_waste_pick_up_sites(self):
		"""
		Creating containers 
		"""
		for i in range(self.num_grey_pickup_sites):
			capacity = random.randint(*self.grey_site_capacity_range)
			self.grey_pick_sites.append(GreyPickUpSite(self.env, i, None, capacity, capacity*random.uniform(*self.grey_site_initial_load_range)))

		#print(self.grey_pick_sites[0].index) #test


	def create_vehicles(self):
		"""
		Initializing vehicles
		"""
		for i in range(self.num_grey_vehicles):
			self.operating_vehicles.append(OperatingVehicle(self.env, self, i, vehicles_config))




	def select_grey_sites(self):
		"""
		Selecting containers based on requesst days old and level of fullment
		"""

		for grey_site in self.grey_pick_sites:
			#print(grey_site.level)
			if grey_site.level >= grey_site.capacity * self.P_VALUE:
				#print(grey_site)
				if not grey_site.request:
					print(f'Initial request range assigned. for {grey_site.index}')
					grey_site.request = random.randint(*self.grey_site_requested_range)
				self.full_grey_sites.append(grey_site)


			# Do we till scheduled sites that are not P full, if the shift is short of tasks

		print("\nSites that are currently full: ")
		print("###########")
		for grey_site in self.full_grey_sites:
			print(grey_site.index, grey_site.request)
		print("###########\n")

		self.full_grey_sites = sorted(self.full_grey_sites, key=lambda x: x.request, reverse=True)

		print("\nSites that are currently full SORTED: ")
		print("###########")
		for grey_site in self.full_grey_sites:
			print(grey_site.index, grey_site.request)
		print("###########\n")

		#yield self.env.timeout(math.ceil(self.env.now / 1440) * 1440 - self.env.now)


	def assign_grey_sites(self):
		"""
		Distribute containers to existing trucks
		"""
		# n_tasks for one truck
		n_tasks = int(self.vehicle_max_runtime / (sum(self.drivetime_range) / 2 + self.loading_time * 2))
		print(f"Approximated numbered of tasks for 1 vehicle for schedulling: {n_tasks}")
		print(f"There are currently {len(self.full_grey_sites)} full grey sites ready, with {self.num_grey_vehicles} vehicles ready for work.")

		routes_list = []
		index_list = list(range(0, len(self.full_grey_sites)))
		index_list = index_list[:n_tasks*self.num_grey_vehicles]
		for i, vehicle in enumerate(self.operating_vehicles):
			route_indexes = [0]
			route_indexes.extend(index_list[i+1::len(self.operating_vehicles)])

			route = []
			for i in route_indexes:
				route.append(self.full_grey_sites[i])

			#print(5555555555, type(route_indexes[1]))
			#print(5555555555, type(route[1]))
			#print(type(self.full_grey_sites[1]))
			vehicle.route = route

			#print(vehicle.index, vehicle.route)

		#yield self.env.timeout(math.ceil(self.env.now / 1440) * 1440 - self.env.now)

	# Create init distance matrix        
	def create_random_distance_matrix(self, symmetrical=True):
		"""
		Imitation of driving time between wste sites
		"""
		num_locations = self.num_grey_pickup_sites
		min = self.drivetime_range[0]
		max = self.drivetime_range[1]
		print(111, num_locations)
		print(type(num_locations))
		num_distances = num_locations*(num_locations - 1)//2
		print(num_distances)
		distance_matrix = np.zeros((num_locations, num_locations), dtype=int)
	
		if symmetrical:
			distance_array = np.random.randint(min, max, size=(num_distances))
	   		# create the distance matrix
			distance_matrix[np.triu_indices(num_locations, k=1)] = distance_array
			distance_matrix += distance_matrix.T
	
		if not symmetrical:
			distance_matrix[np.triu_indices(num_locations, k=1)] = np.random.randint(min, max, size=(num_distances))
			distance_matrix[np.tril_indices(num_locations, k=-1)] = np.random.randint(min, max, size=(num_distances))
		
		for i in distance_matrix:
			print(i)
		
		self.distance_matrix = distance_matrix



	def refill_containers(self): 
		"""
		Add new waste to containers based on their parameters
		"""
		# Daily growth rate
		for container in self.grey_pick_sites:
			container.put(container.daily_growth_rate)
		print("All grey containers are updated!")
		#yield self.env.timeout(math.ceil(self.env.now / 1440) * 1440 - self.env.now)

	def start_daily_shift(self):
		"""
		Daily shift starting
		"""
		for vehicle in self.operating_vehicles:
			self.env.process(vehicle.simulate_route())

		#yield self.env.timeout(math.ceil(self.env.now / 1440) * 1440 - self.env.now)




class Simulation:

	def __init__(self, sim_config):

		self.runtime = sim_config['runtime_days'] * 24 * 60 # Minutes from days
		self.runtime_days = sim_config['runtime_days']


	#def day(self):

	#	yield self.env



	def run(self):
		env = simpy.Environment()
		city_config['env'] = env
		city_config['P_VALUE'] =sim_config['P_VALUE']

		self.city = City(city_config)
		self.city.create_waste_pick_up_sites()
		self.city.create_random_distance_matrix()
		self.city.create_vehicles()
		
		#while True:
		#print(f"Starting for day {i}")
		self.city.select_grey_sites()
		# Clear runtime only not load
		self.city.assign_grey_sites()
		# collect waste
		self.city.start_daily_shift()
		self.city.refill_containers()
		env.timeout(math.ceil(env.now / 1440) * 1440 - env.now)
		env.run(until=self.runtime)
		print(env.now)


		


#known issues
# Extra index at assign signs



# create_containers
# select containers
# assign containers
# create distance matrix
# route 1 vehicle
#	# start
#	# pick up
#	# drop off
#	# break
##	# end
# refill containers

## Tessting field
sim = Simulation(sim_config)
sim.run()