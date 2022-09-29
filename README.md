# Logistics simulation and optimization

A demo of simulation and optimization of glass waste pickup from Rinki sites in the area of the following municipalities in Finland: Hämeenlinna, Hattula, Janakkala, Hausjärvi, Riihimäki, Loppi, Tammela, Forssa, Jokioinen.

<video src='https://user-images.githubusercontent.com/60920087/192505697-90068524-3c6b-4b08-8659-9126d52cef62.mov' width=664></video>

Recyclable glass waste from consumers is constantly accumulating in a number of collection sites ("pickup sites", blue dots on the map), each with a given capacity in tons. Waste is collected and transported to each terminal (red stars) by a truck ("vehicle") starting and finishing their daily 9-hour shift at that terminal. A vehicle can only pick up waste equal to its capacity before it must return to the terminal. Picking up waste at a pickup site takes 15 minutes. Two weeks of waste transportation traffic is simulated, with the routes (as daily lists of pickup sites for each vehicle) optimized by a genetic algorithm utilizing a simulator to calculate and minimize a cost function that depends on the routing. A monetary cost is calculated based on fuel consumption, overtime work, and daily penalties for overfull pickup sites. (Topographic map licensed under CC BY 4.0 by National Land Survey of Finland, retrieved 2022-09.)

![image](https://user-images.githubusercontent.com/60920087/192998041-495b250e-d262-4e15-ae31-f1093a18a166.png)

For more information about Rinki see:
https://rinkiin.fi/tietoa-ringista/suomen-kerayslasiyhdistys/lasipakkausten-terminaalit/
https://rinkiin.fi/kotitalouksille/rinki-ekopisteet/

## Prerequisites

The Python version used is Python 3.10.4.

The Python modules listed in [`/requirements.txt`](requirements.txt) are needed. You can install them by:

`pip install -r requirements.txt`

You need an API key to https://openrouteservice.org/. The key should be stored in `/waste_pickup_sim_secrets.py` in the following format (replace # characters with your key):

`API_key = '########################################################'`

## Compilation and running

### Routing optimizer

To compile the routing optimizer in Windows or Linux:

`g++ routing_optimizer.cpp simcpp/simcpp.cpp -std=c++17 -march=native -I. -O3 -ffast-math -fopenmp -o routing_optimizer`

### Simulation

To run the simulation:

`python routing_optimizer_test.py`

## Copyright and license

Copyright 2022 Häme University of Applied Sciences

Authors: Olli Niemitalo, Genrikh Ekkerman

This work is licensed under both the MIT license and Apache 2.0 license, and is distributed without any warranty.

The source code in the following folders have a separate copyright. 
* [`/nlohmann`](nlohmann) MIT license, see: https://github.com/nlohmann/json
* [`/simcpp`](simcpp) MIT license, see: https://github.com/luteberget/simcpp
