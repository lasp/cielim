#include "ProtobufDirectCommReader.h"
#include <fstream>
#include "ZmqConnection/ZmqMultiThreadActor.h"

ProtobufDirectCommReader::ProtobufDirectCommReader(std::string Connection, UWorld *WorldContext) : SimulationDataSource(Connection)
{
    this->WorldContext = WorldContext;
    // Verify that the version of the library that we linked against is
    // compatible with the version of the headers we compiled against.
    GOOGLE_PROTOBUF_VERIFY_VERSION;
    FVector Location(0.0f, 0.0f, 0.0f);
    FRotator Rotation(0.0f, 0.0f, 0.0f);
    FActorSpawnParameters SpawnInfo;
	// auto actor = this->WorldContext->SpawnActor<AZmqMultiThreadActor>(Location, Rotation, SpawnInfo);
    this->ZmqConnectionActor = std::unique_ptr<AZmqMultiThreadActor>(
        this->WorldContext->SpawnActor<AZmqMultiThreadActor>(Location, Rotation, SpawnInfo));
}

ProtobufDirectCommReader::~ProtobufDirectCommReader()
{
    
}

vizProtobufferMessage::VizMessage& ProtobufDirectCommReader::GetNextSimulationData()
{
    FCircularQueueData NewMessage;
    this->ZmqConnectionActor->GetNextMessageFromQueue(NewMessage);
    this->vizmessage = NewMessage.Message;
    return this->vizmessage;
}
