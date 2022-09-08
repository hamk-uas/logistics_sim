// Copyright 2022 Häme University of Applied Sciences
// Authors: Olli Niemitalo
// 
// This work is licensed under the MIT license and is distributed without any warranty.

// -*- compile-command: "g++ genetic_algorithm_own_test.cpp -std=c++17 -march=native -I. -O3 -ffast-math -fopenmp -o test" -*-

#pragma once

#include <random>
#include <chrono>
#include <algorithm>
#include <limits>
#include <omp.h>
#include <cstddef>

#include "nlohmann/json.hpp"
using json = nlohmann::json;

struct PickupSite {
  float capacity;
  float level;
  float growth_rate;
};

struct RoutingInput {
  std::vector<std::vector<float>> distance_matrix;
  std::vector<PickupSite> pickup_sites;
};

void from_json(const json& j, PickupSite& x) {
    j.at("capacity").get_to(x.capacity);
    j.at("level").get_to(x.level);
    j.at("growth_rate").get_to(x.growth_rate);
}

void from_json(const json& j, RoutingInput& x) {
    j.at("distance_matrix").get_to(x.distance_matrix);
    j.at("pickup_sites").get_to(x.pickup_sites);
}

const int simdIntParallelCount = alignof(std::max_align_t)/sizeof(int); // How many ints fit to the maximum alignment interval

// An optimizer class with will store the population and its costs, and has everything needed for the optimization.
class Optimizer {
 private:
  struct alignas(alignof(std::max_align_t)) aligned_ThreadState {
    std::mt19937 randomNumberGenerator;
    std::uniform_int_distribution<int> uniform1ToNumGenes;
    bool* childHasGene{ nullptr };
  };
  int numGenes;
  int populationSize;
  int *shot;
  int **population;
  int **nextGen;
  const int *distanceMatrix;
  int *nextGenCosts;
  std::mt19937 randomNumberGenerator; // For main thread
  aligned_ThreadState *threadStates; // For parallel threads
  int maxNumThreads;

  // Choose the population size based on numGenes and constructor parameter populationSize
  static int calcPopulationSize(int numGenes, int populationSize) {
    if (populationSize == -1) {
      populationSize = numGenes*4;
      if (populationSize < 100) {
	populationSize = 100;
      }
    }
    return populationSize & -simdIntParallelCount;
  }  

  // Calculate statistics of the population (find the best chromosome)
  void calcStats() {
    bestCost = INT_MAX;
    for (int j = 0; j < populationSize; j++) {
      if (costs[j] < bestCost) {
	bestCost = costs[j];
	best = population[j];
      }
    }    
  }

public:
  int bestCost; // Current best cost
  int *best; // Current best
  int *costs; // Current costs in population

  // Calculate cost of a chromosome
  static int cost(const int* genes, int numGenes, const int* distanceMatrix) {
      int cost = 0;
      for (int i = 0; i < numGenes - 1; i++) {
          int g0 = genes[i];
          int g1 = genes[i + 1];
          cost += distanceMatrix[g0 + numGenes * g1];
      }
      return cost;
  }

  int cost(const int* genes) const {
      return cost(genes, numGenes, distanceMatrix);
  }
   
  // Initialize population and calculate statistics. Called automatically in constructor
  void initPopulation() {
    for (int j = 0; j < populationSize; j++) {
      for (int i = 0; i < numGenes; i++) {
        population[j][i] = i;
      }
      std::shuffle(population[j] + 1, population[j] + numGenes, randomNumberGenerator);
      costs[j] = cost(population[j]);
      nextGen[j][0] = 0;
    }
    calcStats();
  }

  // Cross over two parents and a child. thread = index of the thread that does the work.
  inline void crossover(const int *p0, const int *p1, int *child, int thread) { // Leaves first gene untouched
    std::fill(threadStates[thread].childHasGene, threadStates[thread].childHasGene + numGenes, false);
    int fStart = threadStates[thread].uniform1ToNumGenes(threadStates[thread].randomNumberGenerator);
    int fEnd = threadStates[thread].uniform1ToNumGenes(threadStates[thread].randomNumberGenerator);
    if (fStart > fEnd) std::swap(fStart, fEnd);
    int fLength = fEnd - fStart;
    int ci = 1;
    for (int fi = 0; fi < fLength; ci++, fi++) {
      int gene = p0[fStart + fi];
      child[ci] = gene;
      threadStates[thread].childHasGene[gene] = true;
    }
    for (int p1i = 1; ci < numGenes; ci++, p1i++) {
      for (;threadStates[thread].childHasGene[p1[p1i]]; p1i++);
      child[ci] = p1[p1i];
    }
  }

  // Optimize or continue optimization, over some number of generations
  void optimize(int generations = 10000) {
    for (int j = 0; j < populationSize; j++) {
      shot[j] = j;
    }
    for (int generation = 0; generation < generations; generation++) {
      std::shuffle(shot, shot + populationSize, randomNumberGenerator);
#pragma omp parallel for
      for (int j = 0; j < populationSize; j+= simdIntParallelCount) {
	for (int k = 0; k < simdIntParallelCount; k++) {
	  int p0 = shot[j + k];
	  int p1 = j + k;
	  crossover(population[p0], population[p1], nextGen[j + k], omp_get_thread_num());
	  nextGenCosts[j + k] = cost(nextGen[j + k]);
	  if (nextGenCosts[j + k] > costs[j + k]) {
	    std::swap(population[j + k], nextGen[j + k]);
	    nextGenCosts[j + k] = costs[j + k];
	  }
	}
      }
      std::swap(population, nextGen);
      std::swap(costs, nextGenCosts);
    }
    calcStats();
  }

  // Constructor.
  // numGenes = number of genes per chromosome
  // distanceMatrix = concatenated rows of the distance matrix
  // populationSize = population size, must be a multiple of simdIntParallelCount (typically 4), -1 = auto based on numGenes.
  // seed = random number generator seed. Worker threads use seed + 1, seed + 2, ...
 Optimizer(int numGenes, , int populationSize = -1, unsigned seed = std::chrono::system_clock::now().time_since_epoch().count()): numGenes(numGenes), distanceMatrix(distanceMatrix), populationSize(populationSize = calcPopulationSize(numGenes, populationSize)), randomNumberGenerator(seed), maxNumThreads(omp_get_max_threads())
 {
   threadStates = new aligned_ThreadState[maxNumThreads];   
   for (int thread = 0; thread < maxNumThreads; thread++) {
     threadStates[thread].uniform1ToNumGenes = std::uniform_int_distribution<int>(1, numGenes);
     threadStates[thread].randomNumberGenerator = std::mt19937(seed + 1 + thread); // Use a different seed for each thread
     threadStates[thread].childHasGene = new bool[numGenes];
   }
   shot = new int[populationSize];
   population = new int *[populationSize];
   nextGen = new int *[populationSize];
   costs = new int[populationSize];
   nextGenCosts = new int[populationSize];
   for (int j = 0; j < populationSize; j++) {
     population[j] = new int[numGenes];
     nextGen[j] = new int[numGenes];
   }    
   initPopulation();
 }

  // Destructor
  ~Optimizer() {
    for (int thread = 0; thread < maxNumThreads; thread++) {
        delete[] threadStates[thread].childHasGene;
    }
    delete[] threadStates;
    for (int j = 0; j < populationSize; j++) {
      delete[] population[j];
      delete[] nextGen[j];
    }
    delete[] shot;
    delete[] population;
    delete[] nextGen;
    delete[] costs;
    delete[] nextGenCosts;
  }
};
