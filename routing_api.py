from waste_pickup_sim_secrets import API_key
# waste_pickup_sim_secrets.py contents should be in format (replace # with your API key):
# API_key = '########################################################'

import requests
import numpy as np

def get_distance_and_duration_matrix(coords):
	block_side_length = 50

	distance_matrix = np.ndarray((len(coords), len(coords)), dtype=np.float64)
	duration_matrix = np.ndarray((len(coords), len(coords)), dtype=np.float64)

	block_corners = np.arange(0, len(coords), block_side_length).tolist()
	if block_corners[-1] < len(coords):
		block_corners.append(len(coords))

	for i in range(len(block_corners) - 1):
		for j in range(len(block_corners) - 1):
			source_indexes = np.arange(block_corners[i], block_corners[i + 1]).tolist()
			destination_indexes = np.arange(block_corners[j], block_corners[j + 1]).tolist()
			print("Making a routing API request")
			api_results = api_request_distance_and_duration_matrix(coords, source_indexes, destination_indexes)
			distance_matrix[block_corners[i]:block_corners[i + 1], block_corners[j]:block_corners[j + 1]] = api_results['distance_matrix']
			duration_matrix[block_corners[i]:block_corners[i + 1], block_corners[j]:block_corners[j + 1]] = api_results['duration_matrix']

	return {
		"distance_matrix": distance_matrix,
		"duration_matrix": duration_matrix,
	}

def api_request_distance_and_duration_matrix(coords, source_indexes, destination_indexes):
	"""Function to make an API request for a distance matrix and a duration matrix"""

	headers = {
		'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
		'Authorization': API_key,
		'Content-Type': 'application/json; charset=utf-8'
	}
	
	body = {
		"locations": coords,
		"sources": source_indexes,
		"destinations": destination_indexes,
		"metrics": ["distance", "duration"]
	}
	
	response = requests.post('https://api.openrouteservice.org/v2/matrix/driving-car', json=body, headers=headers)
	response.raise_for_status()
	response_json = response.json()

	return {
		'distance_matrix': np.array(response_json["distances"], dtype=np.float64),
		'duration_matrix': np.array(response_json["durations"], dtype=np.float64)/60 # Convert from seconds to minutes
	}
