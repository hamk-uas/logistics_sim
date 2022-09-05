#pragma once

extern "C" __declspec(dllexport) int optimize(int numGenes, const int *distanceMatrix, int *optimized);
extern "C" __declspec(dllexport) int calc_cost(int numGenes, const int* distanceMatrix, const int* chromosome);
