import math
import numpy
import simpy
import random


TRUCK_CAPACITY = 6
N_TRUCKS = 2


# Create init distance matrix
def create_distance_matrix(pattern_size, min, max, symmetrical=True):
	"""
	"""

	if symmetrical:
		pattern = []	
		for i in range(pattern_size):
			pattern.append(random.randint(min, max))	
		#print(pattern)
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


def create_sites(route, min, max):
	sites = {}
	for site in route:
		sites[f'{site}'] = random.randint(min, max)

	return sites


def waste_sites(env, sites):
	"""
	"""
	containers = {}
	for i in sites.keys():
		containers[i] = simpy.Container(env, capacity=10)
		containers[i].put(sites[i])
		print(f"On waste site #{i} there are currently {sites[i]} tonns at {env.now}")

	return containers


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


def gray_shift(env, distance_matrix, route, truck):
	"""
	"""
	

	
	
	sites = create_sites(route, 9, 10)
	
	
	


	gray_sites = waste_sites(env, sites)

	
	route_shift = env.process(gray_truck_route(env, truck, route, gray_sites, distance_matrix))

	yield env.timeout(0)


def day_shift(a, b, c):
	print(a)
	print(b)
	print(c)


	env = simpy.Environment()

	distance_matrix = create_distance_matrix(48, 5, 25, symmetrical=True)
	print()
	for i in distance_matrix:
		print(i)
	print()
	print()
	route = create_route(distance_matrix)
	print(len(route[1:]))

	chunk_size = len(route[1:]) // N_TRUCKS
	
	if N_TRUCKS > 1:
		if len(route[1:]) % 2 == 0:
			ordered_routes =[route[1:][i:i + chunk_size] for i in range(0, len(route[1:]), chunk_size)]	
	
		elif len(route[1:]) % 2 == 1: 
			ordered_routes =[route[1:][i:i + chunk_size] for i in range(0, len(route[1:]), chunk_size)]
			list1 = ordered_routes[-2]
			list2 = ordered_routes[-1]
			list1.extend(list2)
			ordered_routes[-2] = list1
			ordered_routes = ordered_routes[:-1]

		print(route)
		print(ordered_routes)

	else:
		ordered_routes = [route[1:]]
		print(route)
		print(ordered_routes)


	for i, route in enumerate(ordered_routes):
		

		shift = env.process(gray_shift(env, distance_matrix, route, i))

	env.run()

config_dict = {"c":5, "a":1, "b":2}
day_shift(**config_dict)

