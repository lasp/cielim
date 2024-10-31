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

static CommandType ParseCommand(const std::string& CommandString)
{
	static std::unordered_map<std::string, CommandType> const table = {
		{"PING", CommandType::PING},
		{"SIM_UPDATE", CommandType::SIM_UPDATE},
		{"REQUEST_IMAGE", CommandType::REQUEST_IMAGE}
	};
	
	if (const auto it = table.find(CommandString); it != table.end()) {
		return it->second;
	} 
	return CommandType::ERROR;
}