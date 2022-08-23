import pandas as pd
import numpy as np
import geojson

sites_data_file = 'ekopisteet.csv'

df = pd.read_csv(f'geo_data/{sites_data_file}')

print(df.size)