import math
import simpy
import random
import numpy as np
import queue as queue


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


class PickupSite():

	def log(self, message):
		self.sim.log(f"Pickup site #{self.index}: {message}")

	def warn(self, message):
		self.sim.warn(f"Pickup site #{self.index}: {message}")

	def __init__(self, sim, index):
		self.sim = sim
		self.index = index

		self.capacity = self.sim.config['pickup_sites'][index]['capacity']
		self.level = self.sim.config['pickup_sites'][index]['level']
		self.log(f"Initial level: {tons_to_string(self.level)} / {tons_to_string(self.capacity)} ({to_percentage_string(self.level / self.capacity)})")
		self.levelListeners = []

		self.daily_growth_rate = self.sim.config['pickup_sites'][index]['daily_growth_rate']
		self.log(f"Growth rate: {tons_to_string(self.daily_growth_rate)} / day")

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

	def __init__(self, sim, index):
		self.sim = sim
		self.index = index

		self.load_capacity = sim.vehicle_config["load_capacity"]
		self.load_level = 0

		self.route = []
		self.depart_index = None
		self.depart_time = None

	def get_location(self):
		return None # *** Todo

	def put_load(value):
		self.load_level += value
		self.log(f"Load level increased to {tons_to_string(self.load_level)} / {tons_to_string(self.load_capacity)} ({to_percentage_string(self.load_level/self.load_capacity)})")
		if (self.load_level > self.capacity):
			self.warn("Overload")


class PickupSiteOperator():	

	def log(self, message):
		self.sim.log(f"Pickup site operator #{self.index}: {message}")

	def warn(self, message):
		self.sim.warn(f"Pickup site operator #{self.index}: {message}")

	def __init__(self, sim, index):
		self.sim = sim
		self.index = index
		self.pickup_sites = []

	def assign_as_operator_of_pickup_site(self, site):
		self.pickup_sites.append(site)
		threshold = self.sim.fleet_operator_config["relative_level_threshold_for_pickup"]*site.capacity
		self.log(f"Set threshold {tons_to_string(threshold)} for site {site.index}")


class WastePickupSimulation():

	def log(self, message):
		print(f"{time_to_string(self.env.now)} - {message}")

	def warn(self, message):
		print(f"{time_to_string(self.env.now)} WARNING - {message}")	

	def __init__(self, config):
		self.config = config
		self.locations = list(map(lambda x: x['coordinates'], [*config['pickup_sites'], *config['terminals'], *config['depots']]))

	def site_full(self, site):
		self.warn(f"Site #{site.index} is full.")

	def daily_monitoring(self):
		while True:
			self.log(f"Monitored levels: {', '.join(map(lambda x: to_percentage_string(x.level/x.capacity), self.pickup_sites))}")
			yield self.sim.env.timeout(24*60) # Could be infinitely long

	def sim_init(self):
		self.env = simpy.Environment()
		self.pickup_sites = [PickupSite(self, i) for i in range(self.area_config["num_pickup_sites"])]
		for site in self.pickup_sites:
			site.addLevelListener(self.site_full, site.capacity, {"site": site})
		self.daily_monitoring_activity = self.env.process(self.daily_monitoring())
		self.vehicles = [Vehicle(sim, self, i) for i in range(self.config["num_vehicles"])]

	def sim_run(self):
		self.env.run(until=self.sim_config["runtime_days"]*24*60)
		self.log("Simulation finished")