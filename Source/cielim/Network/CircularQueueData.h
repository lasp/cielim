#pragma once

#include "CoreMinimal.h"

#include "../Protobuf/cielimMessage.pb.h"

// List of recognized commands
enum class CommandType
{
	ERROR,
	PING,
	INIT_SCENE,
	SIM_UPDATE,
	REQUEST_IMAGE,
	NEW_SCENE,
	REMOVE_SCENE,
};

// Payload definitions

struct FNoPayload
{
	// This is an empty payload, used for commands that do not require any additional data.
};

struct FUpdatePayload
{
	TSharedPtr<cielimMessage::CielimMessage> message;

	FUpdatePayload() { message = MakeShared<cielimMessage::CielimMessage>(); }
};

struct FImagePayload
{
	TArray64<uint8> image_data;
	TOptional<FVector2d> centerOfBrightness;

	bool shouldReturnImage;

	FImagePayload() : shouldReturnImage(false) {}
};

struct FCircularQueueData
{
	// Scene ID of the client (only important for inbound data)
	uint8 SceneID;
	// ID of the client tied to this data
	TArray<uint8> ID;
	// Whether that client uses empty delimiters
	bool bUseDelim;
	// Defines which command we're dealing with
	CommandType query;
	// Payload whose type depends on the query
	TVariant<FNoPayload, FUpdatePayload, FImagePayload> payload;

	// Define default states (payload defaults to monostate)
	FCircularQueueData() : SceneID(0), bUseDelim(false), query(CommandType::ERROR) { payload.Emplace<FNoPayload>(); }
};
