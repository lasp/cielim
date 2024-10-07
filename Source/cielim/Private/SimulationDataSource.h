#pragma once

#include "CoreMinimal.h"
#include "cielimMessage.pb.h"
#include <string>

class SimulationDataSource
{
public:
	SimulationDataSource(std::string Source) {};
	virtual ~SimulationDataSource() = default;
	virtual cielimMessage::CielimMessage& GetNextSimulationData() = 0;
};
