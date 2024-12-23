#pragma once

#include "cielimMessage.pb.h"

enum class CommandType
{
	PING,
	SIM_UPDATE,
	REQUEST_IMAGE,
	ERROR
};

class Command
{
public:
	CommandType type{};
};

class Ping : Command
{
public:
	CommandType type=CommandType::PING;
};

class SimUpdate : Command
{
public:
	CommandType type=CommandType::SIM_UPDATE;
	cielimMessage::CielimMessage payload{};
};

class RequestImage : Command
{
public:
	CommandType type=CommandType::REQUEST_IMAGE;
	bool ShouldReturnImage=false;
	std::vector<uint8> payload{};
	std::optional<FVector2d> CenterOfBrightness{};
};

class BSKError : Command
{
public:
	CommandType type=CommandType::ERROR;
};
