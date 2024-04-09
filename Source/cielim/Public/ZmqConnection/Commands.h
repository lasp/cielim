#pragma once

#include "vizMessage.pb.h"

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
	vizProtobufferMessage::VizMessage payload{};
};

class RequestImage : Command
{
public:
	CommandType type=CommandType::REQUEST_IMAGE;
	TArray<uint8> payload{};
};

class BSKError : Command
{
public:
	CommandType type=CommandType::ERROR;
};
