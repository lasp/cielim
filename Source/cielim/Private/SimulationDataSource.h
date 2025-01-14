#pragma once

#include "CoreMinimal.h"
#include "FCielimMessage.h"
#include <optional>
#include <string>

class SimulationDataSource
{
public:
	SimulationDataSource(std::string Source) {};
	virtual ~SimulationDataSource() = default;
	virtual TOptional<FCielimMessage> GetNextSimulationData() = 0;
};
