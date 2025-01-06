#pragma once

#include <variant>
#include <optional>

#include "CoreMinimal.h"
#include "cielimMessage.pb.h"

// List of recognized commands
enum class CommandType
{
	ERROR,
	PING,
	SIM_UPDATE,
	REQUEST_IMAGE,
};

// Payload definitions

struct FUpdatePayload
{
    cielimMessage::CielimMessage message;
};

struct FImagePayload
{
    std::vector<uint8> image_data;
    std::optional<FVector2d> centerOfBrightness;

    bool shouldReturnImage;

    FImagePayload(): shouldReturnImage(false) {}
};

struct FCircularQueueData
{
    // Defines which command we're dealing with
    CommandType query;
    // Payload whose type depends on the query
    TVariant<FUpdatePayload, FImagePayload> payload;

    // Define default states (payload defaults to monostate)
    FCircularQueueData() : query(CommandType::ERROR) {}

};
