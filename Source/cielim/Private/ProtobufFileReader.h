// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "SimulationDataSource.h"
#include "vizMessage.pb.h"
#include <google/protobuf/io/coded_stream.h>
#include <fstream>

/**
 * 
 */
class CIELIM_API ProtobufFileReader : public SimulationDataSource
{
public:
	ProtobufFileReader(std::string Filename);
	~ProtobufFileReader();

	vizProtobufferMessage::VizMessage& GetNextSimulationData() override;

	bool get_eof() const { return Eof; }

private:
	vizProtobufferMessage::VizMessage VizMessage;
	std::fstream Input;
	std::unique_ptr<google::protobuf::io::ZeroCopyInputStream> RawInput;
	std::unique_ptr<google::protobuf::io::CodedInputStream> CodedInput;
	bool Eof;
};

