// Copyright 2022 Häme University of Applied Sciences
// Authors: Olli Niemitalo, Genrikh Ekkerman
//
// This work is licensed under the MIT license and is distributed without any warranty.

// g++ routing_optimizer.cpp simcpp/simcpp.cpp -std=c++17 -march=native -I. -O3 -ffast-math -fopenmp -o routing_optimizer
#include <stdio.h>
#include "ga.h"
#include <iostream>
#include <fstream>
#include <string>
#include <chrono>
#include <algorithm>
#include <omp.h>

#include "nlohmann/json.hpp"
#include "simcpp/simcpp.h"
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

/*
	routing_output = {
		'vehicles': [{
			'route': route
		} for route in vehicle_routes]
	}
	*/

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
};

// Pickup site class definition and member function definitions
class alignas(alignof(std::max_align_t)) PickupSite {
public:
  LogisticsSimulation *logisticsSim;
  float level;
  PickupSite(LogisticsSimulation *logisticsSim):
  logisticsSim(logisticsSim) {}
};

// Vehicle class definition and member function definitions
class alignas(alignof(std::max_align_t)) Vehicle {
private:
public:
  LogisticsSimulation *logisticsSim;
  float loadLevel;
  float odometer; // Total distance traveled
  float overtime; // Total overtime accumulated
  std::vector<int> routeStartLoci;
  Vehicle(LogisticsSimulation *logisticsSim):
  logisticsSim(logisticsSim), routeStartLoci(logisticsSim->routingInput.sim_duration_days) { }
};

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

class VehicleShiftProcess: public simcpp::Process {  
public:
  // Necessary variables
  Vehicle *vehicle;
  int vehicleIndex;
  int day;

  // State variables
  int locus;

  // Quick access variables to make code easier to read
  LogisticsSimulation *logisticsSim;
  RoutingInput &routingInput;
  int homeDepotIndex;
  double shiftStartTime;

  // temporary variables to make code easier to read
  int pickupSiteIndex;
  int sourceLocationIndex;
  int destinationLocationIndex;
  float shiftDuration;

  bool Run() override {
    auto sim = this->sim.lock();

    PT_BEGIN();

    logisticsSim = vehicle->logisticsSim;
    vehicleIndex = vehicle - &logisticsSim->vehicles[0];
    locus = vehicle->routeStartLoci[day];
    routingInput = logisticsSim->routingInput;
    homeDepotIndex = routingInput.vehicles[vehicleIndex].home_depot_index;
    shiftStartTime = sim->get_now();

    //if (debug >= 2) printf("%g Vehicle #%d: day %d route starts at locus %d with gene %d\n", sim->get_now()/60, vehicleIndex, day, locus, logisticsSim->genome[locus]);
    if (logisticsSim->genome[locus] >= routingInput.num_pickup_site_visits_in_genome) {
      // Empty route
      if (debug >= 2) printf("%g Vehicle #%d: no route for day %d\n", sim->get_now()/60, vehicleIndex, day);
    } else {
      // At least one pickup site to visit. First do the step from depot to first place
      if (debug >= 2) printf("%g Vehicle #%d: depart from depot #%d\n", sim->get_now()/60, vehicleIndex, homeDepotIndex);
      sourceLocationIndex = routingInput.depots[homeDepotIndex].location_index;
      pickupSiteIndex = routingInput.gene_to_pickup_site_index[logisticsSim->genome[locus]];
      destinationLocationIndex = routingInput.pickup_sites[pickupSiteIndex].location_index;
      PROC_WAIT_FOR(sim->timeout(routingInput.duration_matrix[sourceLocationIndex][destinationLocationIndex] + pickup_duration));
      vehicle->odometer += routingInput.distance_matrix[sourceLocationIndex][destinationLocationIndex];
      if (debug >= 2) printf("%g Vehicle #%d: arrive at pickup site #%d\n", sim->get_now()/60, vehicleIndex, routingInput.gene_to_pickup_site_index[logisticsSim->genome[locus]]);
      logisticsSim->pickup(vehicleIndex, pickupSiteIndex);
      // From a pickup site to another
      for (; locus + 1 < routingInput.num_genes; locus++) {
        //if (debug >= 2) printf("%g Vehicle #%d: gene = %d\n", sim->get_now()/60, vehicleIndex, logisticsSim->genome[locus + 1]);
        if (logisticsSim->genome[locus + 1] < routingInput.num_pickup_site_visits_in_genome) {
          if (debug >= 2) printf("%g Vehicle #%d: depart from pickup site #%d\n", sim->get_now()/60, vehicleIndex, routingInput.gene_to_pickup_site_index[logisticsSim->genome[locus]]);
          sourceLocationIndex = routingInput.pickup_sites[routingInput.gene_to_pickup_site_index[logisticsSim->genome[locus]]].location_index;
          pickupSiteIndex = routingInput.gene_to_pickup_site_index[logisticsSim->genome[locus + 1]];
          destinationLocationIndex = routingInput.pickup_sites[pickupSiteIndex].location_index;
          PROC_WAIT_FOR(sim->timeout(routingInput.duration_matrix[sourceLocationIndex][destinationLocationIndex] + pickup_duration));
          vehicle->odometer += routingInput.distance_matrix[sourceLocationIndex][destinationLocationIndex];
          if (debug >= 2) printf("%g Vehicle #%d: arrive at pickup site #%d\n", sim->get_now()/60, vehicleIndex, routingInput.gene_to_pickup_site_index[logisticsSim->genome[locus + 1]]);
          logisticsSim->pickup(vehicleIndex, pickupSiteIndex);
        } else {
          break;
        }
      }
      // And finally from the last pickup site back to depot
      if (debug >= 2) printf("%g Vehicle #%d: depart from pickup site #%d\n", sim->get_now()/60, vehicleIndex, routingInput.gene_to_pickup_site_index[logisticsSim->genome[locus]]);
      sourceLocationIndex = routingInput.pickup_sites[routingInput.gene_to_pickup_site_index[logisticsSim->genome[locus]]].location_index;
      destinationLocationIndex = routingInput.depots[homeDepotIndex].location_index;
      PROC_WAIT_FOR(sim->timeout(routingInput.duration_matrix[sourceLocationIndex][destinationLocationIndex]));
      vehicle->odometer += routingInput.distance_matrix[sourceLocationIndex][destinationLocationIndex];
      if (debug >= 2) printf("%g Vehicle #%d: arrive at depot #%d and dump all %g\n", sim->get_now()/60, vehicleIndex, homeDepotIndex, vehicle->loadLevel);
      vehicle->loadLevel = 0;
    }

    shiftDuration = sim->get_now() - shiftStartTime;
    if (shiftDuration > routingInput.vehicles[vehicleIndex].max_route_duration) {
      vehicle->overtime += shiftDuration - routingInput.vehicles[vehicleIndex].max_route_duration;
    }

    PT_END();    
  }

  explicit VehicleShiftProcess(simcpp::SimulationPtr sim, Vehicle *vehicle, int day): 
  Process(sim), vehicle(vehicle), day(day), routingInput(vehicle->logisticsSim->routingInput) { }
};

class DailyProcess: public simcpp::Process {
public:  
  int day;
  int vehicleIndex;
  int pickupSiteIndex;
  LogisticsSimulation *logisticsSim;

  bool Run() override {
    auto sim = this->sim.lock();    

    PT_BEGIN();

    logisticsSim->totalNumPickupSiteOverloadDays = 0;

    for (day = 0; day < logisticsSim->routingInput.sim_duration_days; day++) {
      for (vehicleIndex = 0; vehicleIndex < logisticsSim->vehicles.size(); vehicleIndex++) {
        // Start vehicle shift for current day
        sim->start_process<VehicleShiftProcess>(&logisticsSim->vehicles[vehicleIndex], day);
      }
      PROC_WAIT_FOR(sim->timeout(24*60));
      // Increase pickup site levels
      for (pickupSiteIndex = 0; pickupSiteIndex < logisticsSim->pickupSites.size(); pickupSiteIndex++) {          
        logisticsSim->pickupSites[pickupSiteIndex].level += logisticsSim->routingInput.pickup_sites[pickupSiteIndex].growth_rate*24*60;
        if (logisticsSim->pickupSites[pickupSiteIndex].level > logisticsSim->routingInput.pickup_sites[pickupSiteIndex].capacity) {
          logisticsSim->totalNumPickupSiteOverloadDays++;
          if (debug >= 2) printf("%g WARNING Site %d overload\n", sim->get_now(), pickupSiteIndex);
        }
      }
      for (pickupSiteIndex = 0; pickupSiteIndex < logisticsSim->pickupSites.size(); pickupSiteIndex++) {
        if (debug >= 2) printf("%d\%, ", (int)floor(logisticsSim->pickupSites[pickupSiteIndex].level / logisticsSim->routingInput.pickup_sites[pickupSiteIndex].capacity * 100 + 0.5));
      }
      if (debug >= 2) printf("\n");
    }

    PT_END();    
  }

  explicit DailyProcess(simcpp::SimulationPtr sim, LogisticsSimulation *logisticsSim): 
  Process(sim), logisticsSim(logisticsSim) { }
};

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
  auto sim = simcpp::Simulation::create();
  sim->start_process<DailyProcess>(this);
  sim->run();
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
  return totalOdometer*(50.0/100000.0*2) // Fuel price: 2 eur / L, fuel consumption: 50 L / (100 km)
  + totalNumPickupSiteOverloadDays*50.0 // Penalty of 50 eur / overload day / pickup site
  + totalOvertime*(50.0/60); // Cost of 50 eur / h for overtime work
}

// Simulation class constructor
LogisticsSimulation::LogisticsSimulation(RoutingInput &routingInput):
  routingInput(routingInput), vehicles(routingInput.vehicles.size(), this), pickupSites(routingInput.pickup_sites.size(), this) {
}

int main() {
  std::ifstream f("temp/routing_input.json");
  RoutingInput routingInput(json::parse(f).get<RoutingInput>());
  std::vector<HasCostFunction*> logisticsSims;
  for (int i = 0; i < omp_get_max_threads(); i++) {
    logisticsSims.push_back(new LogisticsSimulation(routingInput));
  }
  /*
  int *testGenome = new int[routingInput.num_genes];
  for (int i = 0; i < routingInput.num_genes; i++) {
    testGenome[i] = i;
  }
  logisticsSims[0]->costFunction(testGenome);
  */

  Optimizer optimizer(routingInput.num_genes, logisticsSims);
  int numGenerations = 2000; // 200000
  int numGenerationsPerStep = 100;
  optimizer.initPopulation();
  /*
  debug = 2;
  for (int i = 0; i < routingInput.num_genes; i++) {
    printf("%d,%d\n", i, optimizer.population[0][i]);
  }
  printf("\n");
  logisticsSims[0]->costFunction(optimizer.population[0]);
  debug = 1;
  */
  int generationIndex = 0;
  for (; generationIndex < numGenerations; generationIndex += numGenerationsPerStep) {
    if (debug >= 1) printf("%d,%f\n", generationIndex, optimizer.bestCost);
    optimizer.optimize(numGenerationsPerStep);
  }
  if (debug >= 1) printf("%d,%f\n", generationIndex, optimizer.bestCost);

  debug++;/*
  for (int i = 0; i < routingInput.num_genes; i++) {
    printf("%d,%d\n", i, optimizer.best[i]);
  }
  printf("\n");*/
  logisticsSims[0]->costFunction(optimizer.best);
  debug--;

  for (int i = 0; i < omp_get_max_threads(); i++) {
    delete logisticsSims[i];
  }

  // Get routes
  int *genome = optimizer.best;
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
