#pragma once

#include "cielimMessage.pb.h"

// Wrapper struct to hold Cielim protobuf
struct FCielimMessage
{
private:
	std::shared_ptr<cielimMessage::CielimMessage> Message;

public:
	FCielimMessage()
	{
		Message = std::make_shared<cielimMessage::CielimMessage>();
		// UE_LOG(LogTemp, Warning, TEXT("Wrapper constructed at %p"), this);
	}
	~FCielimMessage()
	{
		// UE_LOG(LogTemp, Warning, TEXT("Wrapper destructed at %p"), this);
	}

	const cielimMessage::CielimMessage &GetMessage() const { return *Message; }
	cielimMessage::CielimMessage &GetMessageModifiable() const { return *Message; }
};
