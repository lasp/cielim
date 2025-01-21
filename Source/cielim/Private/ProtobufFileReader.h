// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include <fstream>

#include "CoreMinimal.h"
#include "google/protobuf/io/coded_stream.h"

#include "FCielimMessage.h"
#include "SimulationDataSource.h"

/**
 *
 */
class CIELIM_API ProtobufFileReader : public SimulationDataSource
{
public:
	ProtobufFileReader(std::string Filename);
	~ProtobufFileReader();

	TOptional<FCielimMessage> GetNextSimulationData() override;

	bool get_eof() const { return Eof; }

private:
	std::ifstream Input;
	std::unique_ptr<google::protobuf::io::ZeroCopyInputStream> RawInput;
	std::unique_ptr<google::protobuf::io::CodedInputStream> CodedInput;
	bool Eof{};
};
