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
	ProtobufFileReader(std::string filename);
	~ProtobufFileReader();

	vizProtobufferMessage::VizMessage& GetNextSimulationData();

	bool get_eof() const { return eof; }

private:
	vizProtobufferMessage::VizMessage vizmessage;
	std::fstream input;
	google::protobuf::io::ZeroCopyInputStream* raw_input;
	google::protobuf::io::CodedInputStream* coded_input;
	bool eof;
};

