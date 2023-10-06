#pragma once

#include <string>
#include "CoreMinimal.h"
#include "vizMessage.pb.h"

class SimulationDataSource
{
public:
	SimulationDataSource(std::string Source) {};
	virtual ~SimulationDataSource() = default;
	virtual vizProtobufferMessage::VizMessage& GetNextSimulationData() = 0;
};
