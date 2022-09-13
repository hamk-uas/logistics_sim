// -*- compile-command: "g++ ga_test.cpp -std=c++17 -march=native -I. -O3 -ffast-math -fopenmp -o ga_test" -*-
#include <stdio.h>
#include "ga.h"
#include <iostream>
#include <fstream>
#include <string>
#include <chrono>

#include "nlohmann/json.hpp"
using json = nlohmann::json;

struct PickupSite
{
  float capacity;
  float level;
  float growth_rate;
};

struct RoutingInput
{
  std::vector<std::vector<float>> distance_matrix;
  std::vector<PickupSite> pickup_sites;
};

void from_json(const json &j, PickupSite &x)
{
  j.at("capacity").get_to(x.capacity);
  j.at("level").get_to(x.level);
  j.at("growth_rate").get_to(x.growth_rate);
}

void from_json(const json &j, RoutingInput &x)
{
  j.at("distance_matrix").get_to(x.distance_matrix);
  j.at("pickup_sites").get_to(x.pickup_sites);
}

int main() {
  std::ifstream f("routing_input.json");
  Optimizer optimizer(json::parse(f).get<RoutingInput>());
  int numGenerations = 10000;
  optimizer.initPopulation();
  int generationIndex;
  for (generationIndex = 0; generationIndex < numGenerations; generationIndex++) {
    if (generationIndex % 100 == 0) {
      printf("%d: %f", generationIndex, optimizer.bestCost);
    }
  }
  printf("%d: %f,", generationIndex, optimizer.bestCost);
}
