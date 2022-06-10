import math
import numpy
import simpy
import random


# Create init distance matrix
def create_distance_matrix(pattern_size, min, max, symmetrical=True):
	"""
	"""

	if symmetrical:
		pattern = []	
		for i in range(pattern_size):
			pattern.append(random.randint(min, max))	
		print(pattern)
   		# to get the side length, solve for n where len(pattern) = n*(n + 1)/2 (triangular number formula)
		side_length = (int(math.sqrt(1 + 8 * len(pattern))) - 1) // 2 + 1
		assert (side_length * (side_length - 1)) // 2 == len(pattern), "Pattern length must be a triangular number."	
   		# create the grid
		grid = [[0] * side_length for i in range(side_length)]	
   		# fill in the grid
		position = 0
		for i in range(0, side_length - 1):
			for j in range(0, side_length - 1 - i):
				element = pattern[position]; position += 1
				grid[i][i + j + 1] = element # fill in the upper triangle
				grid[i + j + 1][i] = element # fill in the lower triangle	
		return grid

	if not symmetrical:
		pattern = []	
		for i in range(pattern_size):
			pattern.append(random.randint(min, max))	
   		# to get the side length, solve for n where len(pattern) = n*(n + 1)/2 (triangular number formula)
		side_length = (int(math.sqrt(1 + 8 * len(pattern))) - 1) // 2 + 1
		assert (side_length * (side_length - 1)) // 2 == len(pattern), "Pattern length must be a triangular number."	
   		# create the grid
		grid = [[0] * side_length for i in range(side_length)]	
   		# fill in the grid
		position = 0
		for i in range(0, side_length - 1):
			for j in range(0, side_length - 1 - i):
				element = pattern[position]; position += 1
				grid[i][i + j + 1] = element # fill in the upper triangle
				grid[i + j + 1][i] = element + 5 # fill in the lower triangle	# Add assymetry later
		return grid


def create_route(distance_matrix):
	route = list(range(len(distance_matrix)))
	route = random.sample(route[1:], len(route)-1)
	new_route = [0]
	new_route.extend(route)

	return new_route


# Simulation
RANDOM_SEED = 42
N_VEHICLES = 2
CONTAINER_CAPACITY = 3
SHIFT_LENGTH = 600


def warehouse(name, env, store):
	for i in range(100): # Add this growth function later
		yield env.timeout(15)
		yield store.put(f"Item {i}")
		print(f"Item {i} put to pick up at {name} at ", env.now)


def gray_site(name, env, container):
	return

def pick_up_truck(name, env, store, distance_matrix, route):
	while True:
		print(route)
		for warehouse in route[1:]:
			print(f"Truck {name} en route to warehouse {warehouse}")
			#print(distance_matrix[0][route[warehouse]])
			yield env.timeout(distance_matrix[0][route[warehouse]]) # Drive time here		

			
			for tonn in range(CONTAINER_CAPACITY):
				print(name, 'requesting item at', env.now)
				item = yield store.get()
				print(name, 'got item', item, 'at', env.now)
	
			print(f"Truck {name} is full at {env.now}")
	
			yield env.timeout(distance_matrix[route[warehouse]][0]) # Drive to base
			print(f"Truck {name} dropped in base at {env.now}")
			# Wait to drop





def simulate_route_run(env, store, name, distance_matrix, route):
	"""
	"""
	truck = env.process(pick_up_truck(name, env, store, distance_matrix, route))


def simulate_shift():

	# Create a distance matrix
	distance_matrix = create_distance_matrix(6, 15, 30, symmetrical=False)
	for i in distance_matrix:
		print(i)

	n_warehouses = len(distance_matrix)

	env = simpy.Environment()
	store = simpy.Store(env, capacity=100)  # To-pick-up capacity of the warehouse
	#prod = env.process(warehouse(env, store))

	for name in range(n_warehouses):
		prod = env.process(warehouse(name, env, store))
	

	for name in range(N_VEHICLES):
		route = create_route(distance_matrix)
		simulate_route_run(env, store, name, distance_matrix, route)

	env.run(until=SHIFT_LENGTH)

simulate_shift()


