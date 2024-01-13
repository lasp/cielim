// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include <string>
#include "vizMessage.pb.h"
#include <google/protobuf/util/delimited_message_util.h>
#include <google/protobuf/io/zero_copy_stream_impl.h>
#include <google/protobuf/io/coded_stream.h>
#include <fstream>
#include "SimulationDataSource.h"

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

