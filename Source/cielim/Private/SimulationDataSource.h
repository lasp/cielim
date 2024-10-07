#pragma once

#include "CoreMinimal.h"
#include "cielimMessage.pb.h"
#include <optional>
#include <string>

class SimulationDataSource
{
public:
	SimulationDataSource(std::string Source) {};
	virtual ~SimulationDataSource() = default;
	virtual std::optional<cielimMessage::CielimMessage> GetNextSimulationData() = 0;
};
