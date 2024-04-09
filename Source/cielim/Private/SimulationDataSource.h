#pragma once

#include "CoreMinimal.h"
#include "vizMessage.pb.h"
#include <string>

class SimulationDataSource
{
public:
	SimulationDataSource(std::string Source) {};
	virtual ~SimulationDataSource() = default;
	virtual vizProtobufferMessage::VizMessage& GetNextSimulationData() = 0;
};
