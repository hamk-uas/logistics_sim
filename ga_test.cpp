// -*- compile-command: "g++ ga_test.cpp -std=c++17 -march=native -I. -O3 -ffast-math -fopenmp -o ga_test" -*-
#include <stdio.h>
#include "ga.h"
#include <iostream>
#include <fstream>
#include <string>
#include <chrono>

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
