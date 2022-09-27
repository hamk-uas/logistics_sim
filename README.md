# Logistics simulation and optimization

A demo of simulation and optimization of glass waste pickup from Rinki sites in the area of the following municipalities in Finland: Hämeenlinna, Hattula, Janakkala, Hausjärvi, Riihimäki, Loppi, Tammela, Forssa, Jokioinen.

<video src='https://user-images.githubusercontent.com/60920087/192505697-90068524-3c6b-4b08-8659-9126d52cef62.mov' width=664></video>

Topgraphic map licensed under CC BY 4.0 by National Land Survey of Finland, retrieved 2022-09.

For more information about Rinki see:
https://rinkiin.fi/tietoa-ringista/suomen-kerayslasiyhdistys/lasipakkausten-terminaalit/
https://rinkiin.fi/kotitalouksille/rinki-ekopisteet/

## Prerequisities

The Python version used is Python 3.10.4.

The Python modules listed in requirements.txt are needed. You can install them by:<br>
`pip install -r requirements.txt`

You need an API key to https://openrouteservice.org/. The key should be stored in `/waste_pickup_sim_secrets.py` in the following format (replace # with your key):<br>
`API_key = '########################################################'`

## Compilation

### To compile the routing optimizer:
'windows and linux' <br>
`g++ routing_optimizer.cpp simcpp/simcpp.cpp -std=c++17 -march=native -I. -O3 -ffast-math -fopenmp -o routing_optimizer`

To run the simulation:<br>
`python routing_optimizer_test.py`

## Copyright and license

Copyright 2022 Häme University of Applied Sciences
Authors: Olli Niemitalo, Genrikh Ekkerman

This work is licensed under the MIT license and is distributed without any warranty.

The following folders have their separate copyright:
* /nlohmann
* /simcpp
