import simpy
import random
import numpy as np
import pandas as pd

#from grey_site_simulation import OperatingVehicle

P_VALUE = 0.8

DAYS_OLD = [0, 5]

SERVICE_LEVEL_DEADLINE = 7
N_WASTE_PICKUP_SITES = 100
WASTE_CAPACITY = 10
INITIAL_LOAD = [0, 10] # Specify P later
DAYS_TO_FULL = [14, 21] # Normal between that
N_ORDERS = 10

from scipy.stats import truncnorm


def create_city(env, simulation_day, initial_load):

	city = []

	for i in range(N_WASTE_PICKUP_SITES):
		site = {}
		site['index'] = i
		site['request_days_old'] = random.randint(*DAYS_OLD)
		site['site'] = simpy.Container(env, capacity=WASTE_CAPACITY)
		site['site'].put(random.uniform(*initial_load))
		site['daily_growth_rate'] = np.random.normal((DAYS_TO_FULL[0] + DAYS_TO_FULL[1]) / 2, 1, 1) / WASTE_CAPACITY

		city.append(site)

	return city

def select_sites(sites, n_orders):
	# Select top sites based on level and old age

	full_sites = []

	for i in sites:
		#print(i['site'].level)
		if i['site'].level >= WASTE_CAPACITY * P_VALUE:
			full_sites.append(i)

			# Do we till scheduled sites that are not P full, if the shift is short of tasks


	full_sites = sorted(full_sites, key=lambda x: x['request_days_old'], reverse=True)

	print(f"Scheduled {len(full_sites[:n_orders])} from {len(full_sites)} full sites available.")

	return full_sites[:n_orders]


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


def grow(site):
	"""
	linear range between 0 and normal dist of range [14 21]
	"""
	site['site'].put(site['daily_growth_rate'])
	print(f"Site {site['index']} updated.")


def update_city(city):

	for site in city:
		print(site['site'].level)
		grow(site)
		print(site['site'].level)
		print()





def simulate_city():
	env = simpy.Environment()

	# Create city with Sites
	city = create_city(env, DAYS_OLD, INITIAL_LOAD)

	# Select top sites for a shift for a single car
	scheduled_sites = select_sites(city, N_ORDERS)
	for site in scheduled_sites:
		print(site['index'])
		print(site['site'].level)
		print(site['request_days_old'])
		print('######################')

	# Create distance matrix
	scheduled_grid = create_random_distance_matrix(len(scheduled_sites), 5, 30, symmetrical=True)

	# Simulate shift

	# Grow containers level
	update_city(city)


simulate_city()


# City
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


