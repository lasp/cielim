#pragma once
#include "ProtobufFileReader.h"
#include "vizMessage.pb.h"
#include <string>
#include <memory>
#include "Engine/World.h"

#include "ZmqConnection/ZmqMultiThreadActor.h"

class CIELIM_API ProtobufDirectCommReader : public SimulationDataSource
{
public:
	ProtobufDirectCommReader(std::string Connection, UWorld *WorldContext);
	~ProtobufDirectCommReader();

	vizProtobufferMessage::VizMessage& GetNextSimulationData() override;

private:
	UWorld* WorldContext = nullptr;
	std::unique_ptr<AZmqMultiThreadActor> ZmqConnectionActor = nullptr;
	vizProtobufferMessage::VizMessage vizmessage;
};
