#ifdef _MSC_VER
#include "pch.h"
#endif

#include "ga_dll.h"
#include "ga.h"

int optimize(int numGenes, const int* distanceMatrix, int* optimized) {
	Optimizer optimizer(numGenes, distanceMatrix);
	optimizer.optimize();
	int* best = optimizer.best;
	std::copy(best, best + numGenes, optimized);
	return optimizer.bestCost;
}

int calc_cost(int numGenes, const int* distanceMatrix, const int* chromosome) {
	return Optimizer::cost(chromosome, numGenes, distanceMatrix); 
}
