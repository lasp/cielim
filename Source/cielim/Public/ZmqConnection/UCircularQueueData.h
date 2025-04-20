#pragma once

#include "CoreMinimal.h"
#include "FCielimMessage.h"

// List of recognized commands
enum class CommandType
{
	ERROR,
	PING,
	INIT_SCENE,
	SIM_UPDATE,
	REQUEST_IMAGE,
};

// Payload definitions

struct FUpdatePayload
{
	FCielimMessage message;
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
	// ID of the client tied to this data
	TArray<uint8> ID;
	// Whether that client uses empty delimiters
	bool bUseDelim;
	// Defines which command we're dealing with
	CommandType query;
	// Payload whose type depends on the query
	TVariant<FUpdatePayload, FImagePayload> payload;

	// Define default states (payload defaults to monostate)
	FCircularQueueData() : bUseDelim(false), query(CommandType::ERROR) {}
};
