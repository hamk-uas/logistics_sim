// Copyright 2022 Häme University of Applied Sciences
// Authors: Olli Niemitalo, Genrikh Ekkerman
// Based on https://github.com/hamk-uas/assembly-line-sequencing-ga
//
// This work is dual-licensed under the MIT and Apache 2.0 licenses and is distributed without any warranty.

#pragma once

#include <random>
#include <chrono>
#include <algorithm>
#include <limits>
#include <omp.h>
#include <cstddef>
#include <set>
#include <optional>

// A cost function must be provided in an object of a user class that inherits HasCostFunction
template <class T>
class HasCostFunction {
public:
  virtual double costFunction(const std::vector<T> &genome, double earlyOutThreshold = std::numeric_limits<double>::max()) = 0;
};

template <class T>
struct Proposal {
  std::vector<T> genome;
  double cost;

  friend bool operator < (const Proposal &l, const Proposal &r) noexcept {   
    return l.cost < r.cost;
  }

  Proposal(int numGenes): genome(numGenes) {
  }
};

template <class T>
void swap(Proposal<T>& lhs, Proposal<T>& rhs) {
  using std::swap;
  swap(lhs.genome, rhs.genome);
  swap(lhs.cost, rhs.cost);
}

struct ThreadState
{
  std::mt19937 randomNumberGenerator;
  std::uniform_int_distribution<int> uniform0ToNumGenesMinus1;
  std::vector<bool> childHasGene;

  ThreadState(const ThreadState &other):
  uniform0ToNumGenesMinus1(other.uniform0ToNumGenesMinus1.a(), other.uniform0ToNumGenesMinus1.b()),
  childHasGene(childHasGene)
  {}

  ThreadState(int numGenes):
  childHasGene(numGenes, false),
  uniform0ToNumGenesMinus1(0, numGenes - 1)
  {}
};

// An optimizer class that stores the proposal population and its costs, and has everything needed for the optimization.
template <class T>
class Optimizer
{
public:
  int populationSize;
private:
  int maxNumThreads{omp_get_max_threads()};
  int numGenes;
  std::vector<int> proposalIndexPermutation = std::vector<int>(populationSize);
  std::vector<Proposal<T>> children = std::vector<Proposal<T>>(populationSize, numGenes);
  std::vector<HasCostFunction<T>*> &haveCostFunction;
  std::mt19937 randomNumberGenerator; // For main thread
  std::vector<ThreadState> threadStates = std::vector<ThreadState>(maxNumThreads, numGenes);  // For parallel threads

public:
  std::vector<Proposal<T>> population = std::vector<Proposal<T>>(populationSize, numGenes);
  Proposal<T> &best{population[0]}; // Current best proposal

private:
  // Choose the population size based on numGenes and constructor parameter populationSize
  static int calcPopulationSize(int numGenes, int requestedPopulationSize)
  {
    if (requestedPopulationSize == -1)
    {
      requestedPopulationSize = numGenes * 4;
      if (requestedPopulationSize < 100)
      {
        requestedPopulationSize = 100;
      }
    }
    return (requestedPopulationSize + omp_get_max_threads() - 1) / omp_get_max_threads() * omp_get_max_threads();
  }

  // Calculate statistics of the population (find the best chromosome)
  void calcStats()
  {
    best = population[0];
    for (int j = 1; j < populationSize; j++)
    {
      if (population[j].cost < best.cost)
      {
        best = population[j];
      }
    }
  }

public:
  // Initialize population and calculate statistics. Called automatically in constructor
  void initPopulation(std::optional<std::vector<T>> startingPoint = {})
  {
    for (int j = 0; j < populationSize; j++)
    {
      if (startingPoint && j == 0) {
        population[j].genome = *startingPoint;
      } else {
        for (int i = 0; i < numGenes; i++)
        {
          population[j].genome[i] = (T)i;
        }
        std::shuffle(population[j].genome.begin(), population[j].genome.end(), randomNumberGenerator);
      }
      population[j].cost = haveCostFunction[0]->costFunction(population[j].genome);
    }
    calcStats();
  }

  // Cross over two parents and a child. thread = index of the thread that does the work.
  inline void crossover(const std::vector<T> &p0, const std::vector<T> &p1, std::vector<T> &child, int thread)
  { 
    threadStates[thread].childHasGene.assign(numGenes, false); // Fill with false
    int fStart = threadStates[thread].uniform0ToNumGenesMinus1(threadStates[thread].randomNumberGenerator);
    int fEnd = threadStates[thread].uniform0ToNumGenesMinus1(threadStates[thread].randomNumberGenerator);
    int ci0;
    int ci;
    int fi = 0;
    int p1i = fStart;
    if (fStart <= fEnd) {
      // Read fragment from p1 in forward order
      int fLen = fEnd - fStart + 1;
      ci0 = std::uniform_int_distribution<int>(0, numGenes - fLen)(threadStates[thread].randomNumberGenerator);
      ci = ci0;
      for (; p1i <= fEnd && ci < numGenes; ci++, p1i++) {
        T gene = p1[p1i];
        child[ci] = gene;
        threadStates[thread].childHasGene[gene] = true;
      }
    } else {
      // Read fragment from p1 in reverse order
      int fLen = fStart - fEnd + 1;
      ci0 = std::uniform_int_distribution<int>(0, numGenes - fLen)(threadStates[thread].randomNumberGenerator);
      ci = ci0;
      for (; p1i >= fEnd && ci < numGenes; ci++, p1i--) {
        T gene = p1[p1i];
        child[ci] = gene;
        threadStates[thread].childHasGene[gene] = true;
      }
    }
    int ci1 = ci;
    int p0i = 0;
    for (ci = 0; ci < ci0; ci++, p0i++) {
      while (threadStates[thread].childHasGene[p0[p0i]]) {
        p0i++;
      }
      child[ci] = p0[p0i];
    }
    for (ci = ci1; ci < numGenes; ci++, p0i++) {
      while (threadStates[thread].childHasGene[p0[p0i]]) {
        p0i++;
      }
      child[ci] = p0[p0i];
    }
  }

  // Optimize or continue optimization, over some number of generations
  void optimize(int generations = 10000, bool greedy = false)
  {
    for (int generation = 0; generation < generations; generation++) {
      // Create a random permutation of proposal indexes
      if (!greedy) {
        std::shuffle(proposalIndexPermutation.begin(), proposalIndexPermutation.end(), randomNumberGenerator);
      }
      // Make children
#pragma omp parallel for
      for (int j = 0; j < populationSize; j++) {        
        int p0 = j; // Each proposal gets to be a parent 0
        if (!greedy) {
          int p1 = proposalIndexPermutation[j]; // Each proposal is used once per generation as parent 1
          crossover(population[p0].genome, population[p1].genome, children[p0].genome, omp_get_thread_num());
        } else {
          crossover(population[p0].genome, best.genome, children[p0].genome, omp_get_thread_num());
        }
        if (population[p0].genome == children[p0].genome) {
          children[p0].cost = std::numeric_limits<double>::max();
        } else {
          children[p0].cost = haveCostFunction[omp_get_thread_num()]->costFunction(children[p0].genome, population[p0].cost);
        }
      }
      // Child replaces worse parent 0
      for (int j = 0; j < populationSize; j++) {
        if (children[j].cost < population[j].cost) {
          using std::swap;
          swap(population[j], children[j]);            
        }
      }
      calcStats();
    }
  }

  // Constructor.
  // numGenes = number of genes per chromosome
  // distanceMatrix = concatenated rows of the distance matrix
  // populationSize = population size, must be a multiple of simdIntParallelCount (typically 4), -1 = auto based on numGenes.
  // startingPoint = an optional "starting point" genome to be included in the otherwise random population, set to std::nullopt or {} to disable
  // seed = random number generator seed. Worker threads use seed + 1, seed + 2, ...
  Optimizer(int numGenes, std::vector<HasCostFunction<T>*> &haveCostFunction, int requestedPopulationSize = -1, std::optional<std::vector<T>> startingPoint = {}, unsigned seed = std::chrono::system_clock::now().time_since_epoch().count()):
  numGenes(numGenes),
  populationSize(calcPopulationSize(numGenes, requestedPopulationSize)),
  haveCostFunction(haveCostFunction),
  randomNumberGenerator(seed)
  {
    printf("Population size: %d\n", populationSize);
    printf("Numgenes: %d\n", numGenes);
    for (int thread = 0; thread < maxNumThreads; thread++)
    {      
      threadStates[thread].randomNumberGenerator = std::mt19937(seed + 1 + thread); // Use a different seed for each thread      
    }
    initPopulation(startingPoint);
    for (int j = 0; j < populationSize; j++)
    {
      proposalIndexPermutation[j] = j;
    }
  }
};
