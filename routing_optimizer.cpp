// g++ routing_optimizer.cpp -std=c++17 -march=native -I. -O3 -ffast-math -fopenmp -o routing_optimizer
#include <stdio.h>
#include "ga.h"
#include <iostream>
#include <fstream>
#include <string>
#include <chrono>
#include <omp.h>

#include "nlohmann/json.hpp"
using json = nlohmann::json;

struct PickupSiteInput
{
  float capacity;
  float level;
  float growth_rate;
  int location_index;
};

void from_json(const json &j, PickupSiteInput &x)
{
  j.at("capacity").get_to(x.capacity);
  j.at("level").get_to(x.level);
  j.at("growth_rate").get_to(x.growth_rate);
  j.at("location_index").get_to(x.location_index);
}

struct DepotInput
{
  int location_index;
};

void from_json(const json &j, DepotInput &x)
{
  j.at("location_index").get_to(x.location_index);
}

struct TerminalInput
{
  int location_index;
};

void from_json(const json &j, TerminalInput &x)
{
  j.at("location_index").get_to(x.location_index);
}

struct VehicleInput
{
  float load_capacity;
  int home_depot_index;
  int max_route_duration;
};

void from_json(const json &j, VehicleInput &x)
{
  j.at("load_capacity").get_to(x.load_capacity);
  j.at("home_depot_index").get_to(x.home_depot_index);
  j.at("max_route_duration").get_to(x.max_route_duration);
}

struct RoutingInput
{
  std::vector<PickupSiteInput> pickup_sites;
  std::vector<DepotInput> depots;
  std::vector<TerminalInput> terminals;
  std::vector<VehicleInput> vehicles;
  std::vector<std::vector<float>> distance_matrix;
  std::vector<std::vector<float>> duration_matrix;
};

void from_json(const json &j, RoutingInput &x)
{
  j.at("pickup_sites").get_to(x.pickup_sites);
  j.at("depots").get_to(x.depots);
  j.at("terminals").get_to(x.terminals);
  j.at("vehicles").get_to(x.vehicles);
  j.at("distance_matrix").get_to(x.distance_matrix);
  j.at("duration_matrix").get_to(x.duration_matrix);
}

class Vehicle {
public:
  Vehicle() {

  }
};

class Simulation {
public:
  double costFunction(const int *) {    
  }

  Simulation(RoutingInput routingInput) {
  }
};

int main() {
  std::ifstream f("routing_input.json");
  RoutingInput routingInput(json::parse(f).get<RoutingInput>());
  
  /*Optimizer optimizer(routingInput);
  int numGenerations = 10000;
  optimizer.initPopulation();
  int generationIndex;
  for (generationIndex = 0; generationIndex < numGenerations; generationIndex++) {
    if (generationIndex % 100 == 0) {
      printf("%d: %f", generationIndex, optimizer.bestCost);
    }
  }
  printf("%d: %f,", generationIndex, optimizer.bestCost);*/
  return 0;
}
