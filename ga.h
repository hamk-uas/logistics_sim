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

const int simdIntParallelCount = alignof(std::max_align_t) / sizeof(int); // How many ints fit to the maximum alignment interval

// A cost function must be provided in an object of a user class that inherits HasCostFunction
class HasCostFunction {
public:
  virtual double costFunction(const int *genome) = 0;
};

// An optimizer class with will store the population and its costs, and has everything needed for the optimization.
class Optimizer
{
private:
  struct alignas(alignof(std::max_align_t)) aligned_ThreadState
  {
    std::mt19937 randomNumberGenerator;
    std::uniform_int_distribution<int> uniform1ToNumGenes;
    bool *childHasGene{nullptr};
  };
  int numGenes;
  int *shot;
  int **nextGen;
  std::vector<HasCostFunction*> &haveCostFunction;
  double *nextGenCosts;
  std::mt19937 randomNumberGenerator; // For main thread
  aligned_ThreadState *threadStates;  // For parallel threads
  int maxNumThreads;

  // Choose the population size based on numGenes and constructor parameter populationSize
  static int calcPopulationSize(int numGenes, int populationSize)
  {
    if (populationSize == -1)
    {
      populationSize = numGenes * 4;
      if (populationSize < 100)
      {
        populationSize = 100;
      }
    }
    return populationSize & -simdIntParallelCount;
  }

  // Calculate statistics of the population (find the best chromosome)
  void calcStats()
  {
    bestCost = std::numeric_limits<double>::max();
    for (int j = 0; j < populationSize; j++)
    {
      if (costs[j] < bestCost)
      {
        bestCost = costs[j];
        best = population[j];
      }
    }
  }

public:
  int populationSize;
  int **population;
  double bestCost; // Current best cost
  int *best;    // Current best
  double *costs;   // Current costs in population

  // Initialize population and calculate statistics. Called automatically in constructor
  void initPopulation()
  {
    for (int j = 0; j < populationSize; j++)
    {
      for (int i = 0; i < numGenes; i++)
      {
        population[j][i] = i;
      }
      std::shuffle(population[j] + 1, population[j] + numGenes, randomNumberGenerator);      
      costs[j] = haveCostFunction[0]->costFunction(population[j]);
      nextGen[j][0] = 0;
    }
    calcStats();
  }

  // Cross over two parents and a child. thread = index of the thread that does the work.
  inline void crossover(const int *p0, const int *p1, int *child, int thread)
  { // Leaves first gene untouched
    std::fill(threadStates[thread].childHasGene, threadStates[thread].childHasGene + numGenes, false);
    int fStart = threadStates[thread].uniform1ToNumGenes(threadStates[thread].randomNumberGenerator);
    int fEnd = threadStates[thread].uniform1ToNumGenes(threadStates[thread].randomNumberGenerator);
    if (fStart > fEnd)
      std::swap(fStart, fEnd);
    int fLength = fEnd - fStart;
    int ci = 1;
    for (int fi = 0; fi < fLength; ci++, fi++)
    {
      int gene = p0[fStart + fi];
      child[ci] = gene;
      threadStates[thread].childHasGene[gene] = true;
    }
    for (int p1i = 1; ci < numGenes; ci++, p1i++)
    {
      for (; threadStates[thread].childHasGene[p1[p1i]]; p1i++)
        ;
      child[ci] = p1[p1i];
    }
  }

  // Optimize or continue optimization, over some number of generations
  void optimize(int generations = 10000)
  {
    for (int j = 0; j < populationSize; j++)
    {
      shot[j] = j;
    }
    for (int generation = 0; generation < generations; generation++)
    {
      std::shuffle(shot, shot + populationSize, randomNumberGenerator);
#pragma omp parallel for
      for (int j = 0; j < populationSize; j += simdIntParallelCount)
      {
        for (int k = 0; k < simdIntParallelCount; k++)
        {
          int p0 = shot[j + k];
          int p1 = j + k;
          crossover(population[p0], population[p1], nextGen[j + k], omp_get_thread_num());
          nextGenCosts[j + k] = haveCostFunction[omp_get_thread_num()]->costFunction(nextGen[j + k]);
          if (nextGenCosts[j + k] > costs[j + k])
          {
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
  Optimizer(int numGenes, std::vector<HasCostFunction*> &haveCostFunction, int populationSize = -1, unsigned seed = std::chrono::system_clock::now().time_since_epoch().count()) : numGenes(numGenes), haveCostFunction(haveCostFunction), populationSize(populationSize = calcPopulationSize(numGenes, populationSize)), randomNumberGenerator(seed), maxNumThreads(omp_get_max_threads())
  {
    printf("Population size: %d\n", populationSize);
    threadStates = new aligned_ThreadState[maxNumThreads];
    for (int thread = 0; thread < maxNumThreads; thread++)
    {
      threadStates[thread].uniform1ToNumGenes = std::uniform_int_distribution<int>(1, numGenes);
      threadStates[thread].randomNumberGenerator = std::mt19937(seed + 1 + thread); // Use a different seed for each thread
      threadStates[thread].childHasGene = new bool[numGenes];
    }
    shot = new int[populationSize];
    population = new int *[populationSize];
    nextGen = new int *[populationSize];
    costs = new double[populationSize];
    nextGenCosts = new double[populationSize];
    for (int j = 0; j < populationSize; j++)
    {
      population[j] = new int[numGenes];
      nextGen[j] = new int[numGenes];
    }
    initPopulation();
  }

  // Destructor
  ~Optimizer()
  {
    for (int thread = 0; thread < maxNumThreads; thread++)
    {
      delete[] threadStates[thread].childHasGene;
    }
    delete[] threadStates;
    for (int j = 0; j < populationSize; j++)
    {
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
