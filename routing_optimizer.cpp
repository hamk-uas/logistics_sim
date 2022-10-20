// Copyright 2022 Häme University of Applied Sciences
// Authors: Olli Niemitalo, Genrikh Ekkerman
//
// This work is dual-licensed under the MIT and Apache 2.0 licenses and is distributed without any warranty.

// g++ routing_optimizer.cpp simcpp/simcpp.cpp -std=c++20 -march=native -I. -O3 -fcoroutines -ffast-math -fopenmp -o routing_optimizer
#include <stdio.h>
#include "ga.h"
#include <iostream>
#include <fstream>
#include <string>
#include <chrono>
#include <algorithm>
#include <omp.h>
#include <coroutine>
#include "fschuetz04/simcpp20.hpp"
#include "nlohmann/json.hpp"
//#include "simcpp/simcpp.h"
using json = nlohmann::json;

int debug = 1; // 0: no printf, 1: printf for genetic algo, 2: all printf
const float pickup_duration = 15;

struct VehicleOutput {
  std::vector<int> route;
};

struct DayOutput {
  std::vector<VehicleOutput> vehicles;
};

struct RoutingOutput {
  std::vector<DayOutput> days;
};

void to_json(json& j, const VehicleOutput& x) {
  j = json{{"route", x.route}};
}

void to_json(json& j, const DayOutput& x) {
  j = json{{"vehicles", x.vehicles}};
}

void to_json(json& j, const RoutingOutput& x) {
  j = json{{"days", x.days}};
}

struct PickupSiteInput
{
  float capacity;
  float level;
  float growth_rate;
  int location_index;
  int max_num_visits;
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

  // Will be calculated from the above:
  int output_num_days;
  int sim_duration_days;
  int sim_duration;
  std::vector<int> gene_to_pickup_site_index;
  int num_pickup_site_visits_in_genome;
  int num_breaks_in_genome;
  int num_genes;
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

void preprocess_routing_input(RoutingInput &x) {
  // Do some preprocessing calculations
  // Simulation length
  x.output_num_days = 14; // Get routes for 14 days
  x.sim_duration_days = x.output_num_days + 0; // 0 days marginal
  x.sim_duration = x.sim_duration_days*24*60; // * 24h/day * 60min/h
  // The relationship between genes and pickup sites
  x.num_pickup_site_visits_in_genome = 0;
  for (int i = 0; i < x.pickup_sites.size(); i++) {
    PickupSiteInput site = x.pickup_sites[i];
    site.max_num_visits = (int)ceil((site.growth_rate*x.sim_duration + site.level)/(site.capacity*0.8));
    for (int j = x.num_pickup_site_visits_in_genome; j < x.num_pickup_site_visits_in_genome + site.max_num_visits; j++) {
      x.gene_to_pickup_site_index.push_back(i);
    }
    x.num_pickup_site_visits_in_genome += site.max_num_visits;
  }
  if (debug >= 2) printf("num_pickup_site_visits_in_genome = %d\n", x.num_pickup_site_visits_in_genome);
  x.num_breaks_in_genome = ((int)(x.sim_duration / (24*60) + 0.5)) * x.vehicles.size();
  x.num_genes = x.gene_to_pickup_site_index.size() + x.num_breaks_in_genome;
}

// Forward declaration of vehicle and pickup site classes
class Vehicle;
class PickupSite;

// Logistics simulation class definition and member function declarations
class LogisticsSimulation: public HasCostFunction {
public:
  // Config
  simcpp20::simulation<> *sim;
  RoutingInput &routingInput;
  const int *genome;

  // State
  std::vector<Vehicle> vehicles;
  std::vector<PickupSite> pickupSites;
  int totalNumPickupSiteOverloadDays;

  // Member functions
  double costFunction(const int *genome, double earlyOutThreshold = std::numeric_limits<double>::max());
  bool pickup(int vehicleIndex, int pickupSiteIndex);
  
  // Constructor
  LogisticsSimulation(RoutingInput &routingInput);
private:

  simcpp20::event<> runVehicleShiftProcess(simcpp20::simulation<> &sim, int vehicleIndex, int day);
  simcpp20::event<> runDailyProcess(simcpp20::simulation<> &sim);
};

// Pickup site class definition
struct alignas(alignof(std::max_align_t)) PickupSite {
  float level;
};

// Vehicle class definition and member function definitions
struct alignas(alignof(std::max_align_t)) Vehicle {
  float loadLevel;
  float odometer; // Total distance traveled
  float overtime; // Total overtime accumulated
  std::vector<int> routeStartLoci;
  Vehicle(LogisticsSimulation *logisticsSim): routeStartLoci(logisticsSim->routingInput.sim_duration_days) { }
};

simcpp20::event<> LogisticsSimulation::runVehicleShiftProcess(simcpp20::simulation<> &sim, int vehicleIndex, int day) {
  // Necessary variables
  Vehicle* vehicle = &vehicles[vehicleIndex];

  // State variables
  int locus;

  // Quick access variables to make code easier to read
  int homeDepotIndex;
  double shiftStartTime;

  // temporary variables to make code easier to read
  int pickupSiteIndex;
  int sourceLocationIndex;
  int destinationLocationIndex;
  float shiftDuration;

  locus = vehicle->routeStartLoci[day];
  homeDepotIndex = routingInput.vehicles[vehicleIndex].home_depot_index;
  shiftStartTime = sim.now();

  //if (debug >= 2) printf("%g Vehicle #%d: day %d route starts at locus %d with gene %d\n", sim->get_now()/60, vehicleIndex, day, locus, logisticsSim->genome[locus]);
  if (this->genome[locus] >= routingInput.num_pickup_site_visits_in_genome) {
    // Empty route
    if (debug >= 2) printf("%gh Vehicle #%d: no route for day %d\n", sim.now()/60, vehicleIndex, day);
  } else {
    // At least one pickup site to visit. First do the step from depot to first place
    if (debug >= 2) printf("%gh Vehicle #%d: depart from depot #%d\n", sim.now()/60, vehicleIndex, homeDepotIndex);
    sourceLocationIndex = routingInput.depots[homeDepotIndex].location_index;
    pickupSiteIndex = routingInput.gene_to_pickup_site_index[genome[locus]];
    destinationLocationIndex = routingInput.pickup_sites[pickupSiteIndex].location_index;
    co_await sim.timeout(routingInput.duration_matrix[sourceLocationIndex][destinationLocationIndex] + pickup_duration);
    vehicle->odometer += routingInput.distance_matrix[sourceLocationIndex][destinationLocationIndex];
    if (debug >= 2) printf("%gh Vehicle #%d: arrive at pickup site #%d\n", sim.now()/60, vehicleIndex, routingInput.gene_to_pickup_site_index[this->genome[locus]]);
    this->pickup(vehicleIndex, pickupSiteIndex);
    // From a pickup site to another
    for (; locus + 1 < routingInput.num_genes; locus++) {
      //if (debug >= 2) printf("%g Vehicle #%d: gene = %d\n", sim->get_now()/60, vehicleIndex, logisticsSim->genome[locus + 1]);
      if (this->genome[locus + 1] < routingInput.num_pickup_site_visits_in_genome) {
        if (debug >= 2) printf("%gh Vehicle #%d: depart from pickup site #%d\n", sim.now()/60, vehicleIndex, routingInput.gene_to_pickup_site_index[this->genome[locus]]);
        sourceLocationIndex = routingInput.pickup_sites[routingInput.gene_to_pickup_site_index[this->genome[locus]]].location_index;
        pickupSiteIndex = routingInput.gene_to_pickup_site_index[this->genome[locus + 1]];
        destinationLocationIndex = routingInput.pickup_sites[pickupSiteIndex].location_index;
        co_await sim.timeout(routingInput.duration_matrix[sourceLocationIndex][destinationLocationIndex] + pickup_duration);
        vehicle->odometer += routingInput.distance_matrix[sourceLocationIndex][destinationLocationIndex];
        if (debug >= 2) printf("%gh Vehicle #%d: arrive at pickup site #%d\n", sim.now()/60, vehicleIndex, routingInput.gene_to_pickup_site_index[this->genome[locus + 1]]);
        this->pickup(vehicleIndex, pickupSiteIndex);
      } else {
        break;
      }
    }
    // And finally from the last pickup site back to depot
    if (debug >= 2) printf("%gh Vehicle #%d: depart from pickup site #%d\n", sim.now()/60, vehicleIndex, routingInput.gene_to_pickup_site_index[this->genome[locus]]);
    sourceLocationIndex = routingInput.pickup_sites[routingInput.gene_to_pickup_site_index[this->genome[locus]]].location_index;
    destinationLocationIndex = routingInput.depots[homeDepotIndex].location_index;
    co_await sim.timeout(routingInput.duration_matrix[sourceLocationIndex][destinationLocationIndex]);
    vehicle->odometer += routingInput.distance_matrix[sourceLocationIndex][destinationLocationIndex];
    if (debug >= 2) printf("%gh Vehicle #%d: arrive at depot #%d and dump all %g\n", sim.now()/60, vehicleIndex, homeDepotIndex, vehicle->loadLevel);
    vehicle->loadLevel = 0;
  }

  shiftDuration = sim.now() - shiftStartTime;
  if (shiftDuration > routingInput.vehicles[vehicleIndex].max_route_duration) {
    vehicle->overtime += shiftDuration - routingInput.vehicles[vehicleIndex].max_route_duration;
  }
  co_return;
}

simcpp20::event<> LogisticsSimulation::runDailyProcess(simcpp20::simulation<> &sim) {
  
  int day;
  int vehicleIndex;
  int pickupSiteIndex;

  totalNumPickupSiteOverloadDays = 0;

  for (day = 0; day < routingInput.sim_duration_days; day++) {
    for (vehicleIndex = 0; vehicleIndex < vehicles.size(); vehicleIndex++) {
      // Start vehicle shift for current day
      runVehicleShiftProcess(sim, vehicleIndex, day);
    }
    co_await sim.timeout(24*60);
    // Increase pickup site levels
    for (pickupSiteIndex = 0; pickupSiteIndex < pickupSites.size(); pickupSiteIndex++) {          
      pickupSites[pickupSiteIndex].level += routingInput.pickup_sites[pickupSiteIndex].growth_rate*24*60;
      if (pickupSites[pickupSiteIndex].level > routingInput.pickup_sites[pickupSiteIndex].capacity) {
        totalNumPickupSiteOverloadDays++;
        if (debug >= 2) printf("%gh WARNING Site %d overload\n", sim.now()/60, pickupSiteIndex);
      }
    }
    for (pickupSiteIndex = 0; pickupSiteIndex < pickupSites.size(); pickupSiteIndex++) {
      if (debug >= 2) printf("%d%%, ", (int)floor(pickupSites[pickupSiteIndex].level / routingInput.pickup_sites[pickupSiteIndex].capacity * 100 + 0.5));
    }
    if (debug >= 2) printf("\n");
  }

  co_return;
}

bool LogisticsSimulation::pickup(int vehicleIndex, int pickupSiteIndex) {
  if (pickupSites[pickupSiteIndex].level == 0) {
    // Unnecessary visit, nothing to pick up
    if (debug >= 2) printf("Vehicle #%d: nothing to pick up at site #%d\n", vehicleIndex, pickupSiteIndex);
    return false; // No work done
  } else if (vehicles[vehicleIndex].loadLevel == routingInput.vehicles[vehicleIndex].load_capacity) {
    // Unnecessary visit, no unused load capacity left
    if (debug >= 2) printf("Vehicle #%d: has no capacity left to pick anything at pickup site #%d with %f remaining\n", vehicleIndex, pickupSiteIndex, pickupSites[pickupSiteIndex].level);
    return false; // No work done
  } else if (vehicles[vehicleIndex].loadLevel + pickupSites[pickupSiteIndex].level > routingInput.vehicles[vehicleIndex].load_capacity) {
    // The vehicle cannot take everything
    pickupSites[pickupSiteIndex].level -= (routingInput.vehicles[vehicleIndex].load_capacity - vehicles[vehicleIndex].loadLevel);
    if (debug >= 2) printf("Vehicle #%d: reaches its capacity taking %f from pickup site #%d with %f remaining\n", vehicleIndex, routingInput.vehicles[vehicleIndex].load_capacity - vehicles[vehicleIndex].loadLevel, pickupSiteIndex, pickupSites[pickupSiteIndex].level);
    vehicles[vehicleIndex].loadLevel = routingInput.vehicles[vehicleIndex].load_capacity;
    return true; // Some work done
  } else {
    // The vehicle empties the site
    vehicles[vehicleIndex].loadLevel += pickupSites[pickupSiteIndex].level;
    if (debug >= 2) printf("Vehicle #%d: empties all %f of pickup site #%d\n", vehicleIndex, pickupSites[pickupSiteIndex].level, pickupSiteIndex);
    pickupSites[pickupSiteIndex].level = 0;
    return true; // Some work done
  }
}

double costFunctionFromComponents(double totalOdometer, double totalNumPickupSiteOverloadDays, double totalOvertime) {
  return totalOdometer*(50.0/100000.0*2) // Fuel price: 2 eur / L, fuel consumption: 50 L / (100 km)
  + totalNumPickupSiteOverloadDays*50.0 // Penalty of 50 eur / overload day / pickup site
  + totalOvertime*(50.0/60); // Cost of 50 eur / h for overtime work  
}

// Logistics simulation class member function: cost function
double LogisticsSimulation::costFunction(const int *genome, double earlyOutThreshold) {
  // Interpret genome
  this->genome = genome;
  if (debug >= 2) printf("Genome size: %d\n", routingInput.num_genes);
  if (debug >= 2) printf("First non-pickup-site gene: %d\n", routingInput.num_pickup_site_visits_in_genome);
  // Initialize vehicles
  for (int vehicleIndex = 0; vehicleIndex < vehicles.size(); vehicleIndex++) {
    vehicles[vehicleIndex].loadLevel = 0;
    vehicles[vehicleIndex].odometer = 0;
    vehicles[vehicleIndex].overtime = 0;
  }
  // Initialize pickup sites
  for (int pickupSiteIndex = 0; pickupSiteIndex < pickupSites.size(); pickupSiteIndex++) {
    pickupSites[pickupSiteIndex].level = routingInput.pickup_sites[pickupSiteIndex].level;
  }
  totalNumPickupSiteOverloadDays = 0;
  vehicles[0].routeStartLoci[0] = 0;
  if (debug >= 2) printf("Vehicle #%d will start day %d route at locus %d\n", 0, 0, 0);
  int vehicleIndex = 0;
  int day = 0;
  for (int locus = 0; locus < routingInput.num_genes; locus++) {
    if (genome[locus] >= routingInput.num_pickup_site_visits_in_genome) {
      vehicleIndex++;
      if (vehicleIndex >= vehicles.size()) {
        vehicleIndex = 0;
        day++;
        if (day >= routingInput.sim_duration_days) {
          break;
        }
      }
      vehicles[vehicleIndex].routeStartLoci[day] = locus + 1;
      if (debug >= 2) printf("Vehicle #%d start day %d route at locus %d\n", vehicleIndex, day, locus);
    }
  }
  // Simulate
  simcpp20::simulation<> sim;
  this->sim = &sim;
  runDailyProcess(sim);
  sim.run();
  double totalOvertime = 0;
  double totalOdometer = 0;
  for (int vehicleIndex = 0; vehicleIndex < vehicles.size(); vehicleIndex++) {
    totalOvertime += vehicles[vehicleIndex].overtime;
    if (debug >= 2) printf("Vehicle #%d overtime: %g h\n", vehicleIndex, vehicles[vehicleIndex].overtime/60);
    if (debug >= 2) printf("Vehicle #%d odometer reading: %g km\n", vehicleIndex, vehicles[vehicleIndex].odometer/1000);
    totalOdometer += vehicles[vehicleIndex].odometer;
  }
  if (debug >= 2) printf("Total overtime: %g h\n", totalOvertime/60);
  if (debug >= 2) printf("Total odometer: %g km\n", totalOdometer/1000);
  if (debug >= 2) printf("Total pickup site overload days: %d\n", totalNumPickupSiteOverloadDays);
  return costFunctionFromComponents(totalOdometer, totalNumPickupSiteOverloadDays, totalOvertime);
}

// Simulation class constructor
LogisticsSimulation::LogisticsSimulation(RoutingInput &routingInput):
  routingInput(routingInput), vehicles(routingInput.vehicles.size(), this), pickupSites(routingInput.pickup_sites.size()) {
}

int main() {
  // Read routing optimization input
  std::ifstream f("temp/routing_input.json");
  RoutingInput routingInput(json::parse(f).get<RoutingInput>());
  // Preprocess routing optimization input
  preprocess_routing_input(routingInput);
  std::vector<HasCostFunction*> logisticsSims;
  for (int i = 0; i < omp_get_max_threads(); i++) {
    logisticsSims.push_back(new LogisticsSimulation(routingInput));
  }
/*
  int *testGenome = new int[routingInput.num_genes];
  for (int i = 0; i < routingInput.num_genes; i++) {
    testGenome[i] = i;
  }
  logisticsSims[0]->costFunction(testGenome); */

/*
  int testGenome[] = {130,86,59,68,99,101,82,75,79,76,72,84,80,94,28,25,111,30,120,12,6,18,0,2,126,114,104,36,138,117,48,63,67,34,89,93,53,23,90,96,46,41,40,108,43,103,134,132,136,122,137,139,142,143,128,133,129,118,125,131,123,135,116,140,119,121,141,127,124,92,5,100,71,74,85,39,22,81,61,51,113,95,73,106,70,88,11,91,112,109,31,54,16,19,97,98,29,21,57,8,47,58,10,27,7,45,52,32,9,24,55,3,13,87,1,17,115,83,65,37,26,56,60,4,102,105,77,44,49,110,50,20,33,107,69,62,14,35,15,64,38,42,78,66};
  debug++;
  logisticsSims[0]->costFunction(testGenome);
  debug--;*/

  Optimizer optimizer(routingInput.num_genes, logisticsSims);
  int numGenerations = 30000; // 30000
  int numFinetuneGenerations = 10000; // 10000
  int numGenerationsPerStep = 100;
  optimizer.initPopulation();

  int generationIndex = 0;
  for (; generationIndex < numGenerations; generationIndex += numGenerationsPerStep) {
    if (debug >= 1) printf("%d,%f\n", generationIndex, optimizer.bestCost);
    optimizer.optimize(numGenerationsPerStep, 0);
  }
  for (; generationIndex < numGenerations + numFinetuneGenerations; generationIndex += numGenerationsPerStep) {
    if (debug >= 1) printf("%d,%f\n", generationIndex, optimizer.bestCost);
    optimizer.optimize(numGenerationsPerStep, 2);
  }
  if (debug >= 1) printf("%d,%f\n", generationIndex, optimizer.bestCost);

  debug++;
  logisticsSims[0]->costFunction(optimizer.best);
  debug--;

  for (int i = 0; i < omp_get_max_threads(); i++) {
    delete logisticsSims[i];
  }

  // Get routes
  int *genome = optimizer.best;
  printf("\nBest genome:\n");
  for (int i = 0; i < routingInput.num_genes; i++) {
    printf("%d,", genome[i]);
  }
  printf("\n\n");
  RoutingOutput routingOutput;
  LogisticsSimulation logisticsSim(routingInput);
  logisticsSim.costFunction(optimizer.best); // Get routeStartLoci
  for (int day = 0; day < routingInput.output_num_days; day++) {
    DayOutput dayOutput;
    for (int vehicleIndex = 0; vehicleIndex < routingInput.vehicles.size(); vehicleIndex++) {
      VehicleInput &vehicle = routingInput.vehicles[vehicleIndex];
      VehicleOutput vehicleOutput;
      int locus = logisticsSim.vehicles[vehicleIndex].routeStartLoci[day];
      if (genome[locus] >= routingInput.num_pickup_site_visits_in_genome) {
        // No route
      } else {
        // There will be at least one pickup site in the route
        // Depot
        vehicleOutput.route.push_back(routingInput.depots[vehicle.home_depot_index].location_index);
        // Pickup sites
        for (; locus + 1 < routingInput.num_genes; locus++) {
          if (genome[locus] < routingInput.num_pickup_site_visits_in_genome) {
            int pickupSiteIndex = routingInput.gene_to_pickup_site_index[genome[locus]];
            int destinationLocationIndex = routingInput.pickup_sites[pickupSiteIndex].location_index;
            if (destinationLocationIndex != vehicleOutput.route[vehicleOutput.route.size()-1]) {
              vehicleOutput.route.push_back(destinationLocationIndex);
            }
          } else {
            break;
          }
        }
        vehicleOutput.route.push_back(routingInput.depots[vehicle.home_depot_index].location_index);
      }
      dayOutput.vehicles.push_back(vehicleOutput);
    }
    routingOutput.days.push_back(dayOutput);    
  }
  json j = routingOutput;  
  std::ofstream o("temp/routing_output.json");
  o << std::setw(4) << j << std::endl;

  return 0;
}