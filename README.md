# Logistics simulation and optimization

A demo of simulation and optimization of glass waste pickup from Rinki sites in the area of the following municipalities in Finland: Hämeenlinna, Hattula, Janakkala, Hausjärvi, Riihimäki, Loppi, Tammela, Forssa, Jokioinen, chosen arbitrarily. For more information about Rinki see: https://rinkiin.fi/kotitalouksille/rinki-ekopisteet/ and https://rinkiin.fi/tietoa-ringista/suomen-kerayslasiyhdistys/lasipakkausten-terminaalit/.

<video src='https://user-images.githubusercontent.com/60920087/194047546-58bdf96e-0576-477f-b2c4-2b9f55a3a183.mov' width=640></video>

_Animated simulation using optimized routes._

Recyclable glass waste from consumers is constantly accumulating in a number of collection sites ("pickup sites", blue/yellow/red dots on the map, depending on fullness <50%/50-75%/>75%), each with a given capacity in tons. Waste is collected and transported to each terminal (red stars) by a truck ("vehicle") starting and finishing their daily 9-hour shift at that terminal. A vehicle can only pick up waste up to its capacity before it must return to the terminal. Picking up waste at a pickup site takes 15 minutes.

Two weeks of waste transportation traffic is simulated, with the routes (a list of locations for each vehicle, for each day) optimized by a genetic algorithm utilizing a simulator to calculate and minimize a cost function that depends on the routing. A monetary cost is calculated based on fuel consumption, overtime work, and daily penalties for overfull pickup sites. As can be seen in the above animation, the optimization does not care what happens after the two-week period, and many of the pickup sites are almost full at the end.

The simulation type is **process-based discrete event simulation**. The main simulation is implemented in Python using [SimPy](https://simpy.readthedocs.io/en/latest/), and the optimizer uses a faster C++ implementation of the same simulation model using [SimCpp20](https://github.com/fschuetz04/simcpp20).

The simulation model consists of the following types of components:
* **Pickup site** (location)
  * State: level (tons)
  * Properties: capacity (tons), growth rate (tons / day), geographical coordinates
* **Terminal/depot** (location)
  * Properties: number of vehicles, geographical coordinates
* **Vehicle**
  * State: level (tons), moving (boolean),
    * if not moving: location
    * if moving: current route step, start time of current route step
  * Properties: capacity (tons), work shift length (9 hours), routes

To obtain tables of travel times and distances between locations the simulation utilizes a routing API, currently [openrouteservice](https://openrouteservice.org/) but could be changed to [Open Source Routing Machine (OSRM)](https://github.com/Project-OSRM/osrm-backend)

The optimizer uses a genetic algorithm to come up with routing proposals. The cost of each proposal is evaluated using the cost function.

![image](https://user-images.githubusercontent.com/60920087/192998041-495b250e-d262-4e15-ae31-f1093a18a166.png)

_System diagram._

![image](https://user-images.githubusercontent.com/60920087/196900595-75e237a8-362d-48bc-8d74-89732601cc8a.png)

_Optimization trajectory: Lowest cost in the population of route proposals as function of the number of cost function evaluations. That number increases by the population size for every generation of the genetic algorithm. Optimization is done for a predefined number of generations. At a predefined generation, there is a change to a greedy optimization algorithm that always uses the lowest-cost member in the population as one of the parents to generate an offspring route proposal._

## Prerequisites

The Python version used is Python 3.10.4.

The Python modules listed in [`/requirements.txt`](requirements.txt) are needed. You can install them by:

`pip install -r requirements.txt`

You need an API key to [openrouteservice](https://openrouteservice.org/). The key should be stored in `/waste_pickup_sim_secrets.py` in the following format (replace # characters with your key):

`API_key = '########################################################'`

## Compilation and running

### Routing optimizer

To compile the routing optimizer in Windows or Linux:

`g++ routing_optimizer.cpp -std=c++20 -march=native -I. -O3 -fcoroutines -ffast-math -fopenmp -o routing_optimizer`

### Simulation

To run the simulation:

`python waste_pickup_sim_test.py`

## Copyright, license, and credits

Copyright 2022 Häme University of Applied Sciences

Authors: Olli Niemitalo, Genrikh Ekkerman

This work is licensed under both the MIT license and Apache 2.0 license, and is distributed without any warranty.

The source code in the following folders is 3rd-party and has separate copyright and licenses:
* [`/nlohmann`](nlohmann) [JSON for Modern C++](https://github.com/nlohmann/json), MIT license
* [`/fschuetz04`](fschuetz04) [SimCpp20, discrete event simulation in C++ using coroutines](https://github.com/fschuetz04/simcpp20), MIT license

The topographic map shown in this readme file is licensed under CC BY 4.0 by National Land Survey of Finland, retrieved 2022-09.
