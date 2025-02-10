#pragma once

#include <optional>
#include <string>

#include "CoreMinimal.h"

#include "FCielimMessage.h"

class SimulationDataSource
{
public:
	SimulationDataSource(std::string Source) {};
	virtual ~SimulationDataSource() = default;
	virtual TOptional<FCielimMessage> GetNextSimulationData() = 0;
};
