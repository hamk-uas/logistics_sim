// Copyright 2022 Häme University of Applied Sciences
// Authors: Olli Niemitalo, Genrikh Ekkerman
// Based on https://github.com/hamk-uas/assembly-line-sequencing-ga
//
// This work is dual-licensed under the MIT and Apache 2.0 licenses and is distributed without any warranty.

// Compile with one of:
// g++ routing_optimizer.cpp simcpp/simcpp.cpp -std=c++20 -march=native -I. -O3 -fcoroutines -ffast-math -fopenmp -o routing_optimizer
// g++-10 routing_optimizer.cpp simcpp/simcpp.cpp -std=c++20 -march=native -I. -O3 -fcoroutines -ffast-math -fopenmp -o routing_optimizer

#pragma once

#include <random>
#include <chrono>
#include <algorithm>
#include <limits>
#include <omp.h>
#include <cstddef>

// A cost function must be provided in an object of a user class that inherits HasCostFunction
template <class T>
class HasCostFunction {
public:
  virtual double costFunction(const T *genome, double earlyOutThreshold = std::numeric_limits<double>::max()) = 0;
};

template <class T>
struct alignas(alignof(std::max_align_t)) Proposal {
  int numGenes;
  T *genome;
  double cost;

  Proposal(const Proposal &other) {
    numGenes = other.numGenes;
    genome = new T[numGenes];
  }

  Proposal(int numGenes) {
    this->numGenes = numGenes;
    genome = new T[numGenes];
  }

  ~Proposal() {
    delete[] genome;
  }
};

template <class T>
void swap(Proposal<T>& lhs, Proposal<T>& rhs) {
  std::swap(lhs.genome, rhs.genome);
  std::swap(lhs.cost, rhs.cost);
}

struct alignas(alignof(std::max_align_t)) aligned_ThreadState
{
  std::mt19937 randomNumberGenerator;
  std::uniform_int_distribution<int> uniform0ToNumGenesMinus1;
  bool *childHasGene{nullptr};
};

// An optimizer class with will store the population and its costs, and has everything needed for the optimization.
template <class T>
class Optimizer
{
public:
  int populationSize;
private:
  int maxNumThreads;
  int numGenes;
  int *proposalIndexPermutation;
  std::vector<Proposal<T>> children;
  std::vector<HasCostFunction<T>*> &haveCostFunction;
  std::mt19937 randomNumberGenerator; // For main thread
  aligned_ThreadState *threadStates;  // For parallel threads

public:
  std::vector<Proposal<T>> population;
  int best; // Current best index

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
    return requestedPopulationSize / omp_get_max_threads() * omp_get_max_threads();
  }

  // Calculate statistics of the population (find the best chromosome)
  void calcStats()
  {
    best = 0;
    for (int j = 0; j < populationSize; j++)
    {
      if (population[j].cost < population[best].cost)
      {
        best = j;
      }
    }
  }

public:
  // Initialize population and calculate statistics. Called automatically in constructor
  void initPopulation()
  {
    for (int j = 0; j < populationSize; j++)
    {
      for (int i = 0; i < numGenes; i++)
      {
        population[j].genome[i] = (T)i;
      }
      std::shuffle(population[j].genome, population[j].genome + numGenes, randomNumberGenerator);
      population[j].cost = haveCostFunction[0]->costFunction(population[j].genome);
    }
    calcStats();
  }

  // Cross over two parents and a child. thread = index of the thread that does the work.
  inline void crossover(const T *p0, const T *p1, T *child, int thread)
  { 
    std::fill(threadStates[thread].childHasGene, threadStates[thread].childHasGene + numGenes, false);
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
  void optimize(int generations = 10000, bool finetune = false)
  {
    for (int generation = 0; generation < generations; generation++) {
      // Create a random permutation of proposal indexes
      if (!finetune) {
        std::shuffle(proposalIndexPermutation, proposalIndexPermutation + populationSize, randomNumberGenerator);
      }
      // Make children
#pragma omp parallel for
      for (int j = 0; j < populationSize; j++) {        
        int p0 = j; // Each proposal gets to be a parent 0
        if (!finetune) {
          int p1 = proposalIndexPermutation[j]; // Each proposal is used once per generation as parent 1
          crossover(population[p0].genome, population[p1].genome, children[p0].genome, omp_get_thread_num());
        } else {
          crossover(population[p0].genome, population[best].genome, children[p0].genome, omp_get_thread_num());
        }
        children[p0].cost = haveCostFunction[omp_get_thread_num()]->costFunction(children[p0].genome, population[p0].cost);
      }
      // 
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
  // seed = random number generator seed. Worker threads use seed + 1, seed + 2, ...
  Optimizer(int numGenes, std::vector<HasCostFunction<T>*> &haveCostFunction, int requestedPopulationSize = -1, unsigned seed = std::chrono::system_clock::now().time_since_epoch().count()):
  maxNumThreads(omp_get_max_threads()),
  numGenes(numGenes),
  populationSize(calcPopulationSize(numGenes, requestedPopulationSize)),
  haveCostFunction(haveCostFunction),
  randomNumberGenerator(seed),
  best(0),
  population(populationSize, numGenes),
  children(populationSize, numGenes)
  {
    printf("Population size: %d\n", populationSize);
    printf("Numgenes: %d\n", numGenes);
    threadStates = new aligned_ThreadState[maxNumThreads];
    for (int thread = 0; thread < maxNumThreads; thread++)
    {
      threadStates[thread].uniform0ToNumGenesMinus1 = std::uniform_int_distribution<int>(0, numGenes - 1);
      threadStates[thread].randomNumberGenerator = std::mt19937(seed + 1 + thread); // Use a different seed for each thread
      threadStates[thread].childHasGene = new bool[numGenes];
    }
    proposalIndexPermutation = new int[populationSize];
    initPopulation();
    for (int j = 0; j < populationSize; j++)
    {
      proposalIndexPermutation[j] = j;
    }
  }

  // Destructor
  ~Optimizer()
  {
    for (int thread = 0; thread < maxNumThreads; thread++)
    {
      delete[] threadStates[thread].childHasGene;
    }
    delete[] threadStates;
    delete[] proposalIndexPermutation;
  }
};
