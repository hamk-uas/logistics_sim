import simpy


config1 = {'index': 1,
		'env' : simpy.Environment(),
		'type' :'grey',
		'capacity' : 10}

config2 = {'index': 2,
		'env' : simpy.Environment(),
		'type' :'grey',
		'capacity' : 15}

class Truck(simpy.Container):
	def __init__(self, env, capacity, config):
		super().__init__(env, capacity)
		self.index = config['index']
		self.type = config['type']

		

	def start_shift(self):
		self.put(4)
		print(self.level)
		print(f"{self.capacity} tonnes truck {self.index} is starting a {self.type} shift @.")




def simulation():
	env = simpy.Environment()
	capacity = 10
	truck1 = Truck(env, capacity, config1)
	truck2 = Truck(config2['env'], config2['capacity'], config2)
	truck1.start_shift()

	truck2.start_shift()

	return

simulation()
