// -*- compile-command: "g++ ga_test.cpp -std=c++17 -march=native -I. -O3 -ffast-math -fopenmp -o test" -*-
#include <stdio.h>
#include "ga.h"
#include <iostream>
#include <fstream>
#include <string>
#include <chrono>

#include "nlohmann/json.hpp"
using json = nlohmann::json;

int main() {
  std::ifstream f("example.json");
  json data = json::parse(f);
  /*
  Optimizer *optimizer = new Optimizer(M, newMatrix);
  int numGenerations = 10000;
  optimizer->initPopulation();
  for (int generationIndex = 0; generationIndex < numGenerations; generationIndex++) {
    if (generationIndex % 100 == 0) {
      printf("%d: %f", generationIndex, optimizer->bestCost);
    }
  }
  printf("%d: %f,", generationIndex, optimizer->bestCost);
  delete optimizer;
  */
}
