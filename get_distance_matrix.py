from secrets import API_key

from os.path import exists


import json
import requests
import openrouteservice
import pandas as pd

def test():
	print("Testing with some coords we have here...")
	with open('geo_data/sim_test_sites.geojson') as pickup_sites_file:
		pickup_sites_geojson = json.load(pickup_sites_file)
	
	print(pickup_sites_geojson.keys())
	
	df = pd.DataFrame()
	
	for i in range(len(pickup_sites_geojson['features'])):
		df_geometry = pd.DataFrame(pickup_sites_geojson['features'][i]['geometry'])
		df_row = df_geometry['coordinates']
		df = df.append(df_row, ignore_index = True)
	
	print(df.shape)
	coords = df.values.tolist()
	
	print(coords)

	request_distance_matrix(coords)


def process_request(coords):
	if len(coords) * len(coords) >= 3500:
		distance_matrix = request_distance_matrix(coords[:50])




def request_distance_matrix(coords):
	"""Function to make an API request for a distacne matrix"""

	filename = 'geo_data/distance_matrix.json'

	file_exists = exists(filename)

	if not False:

		headers = {
			'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
			'Authorization': API_key,
			'Content-Type': 'application/json; charset=utf-8'
		}
		
		body = {"locations":coords,"metrics":["distance", "duration"]}
		
		response = requests.post('https://api.openrouteservice.org/v2/matrix/driving-car', json=body, headers=headers)
		
		print(response.status_code, response.reason)
		print(response.json())
	
	

		with open('geo_data/distance_matrix.json', 'w') as outfile:
			json.dump(response.json(), outfile, indent=4)

		#print(response.json().keys())

		#print(print(response.json()['metadata']))

		return response.json()['distances']

	else:
		with open(filename, 'r') as file:
			distance_matrix = json.load(file)
		return distance_matrix




