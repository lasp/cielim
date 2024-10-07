// Fill out your copyright notice in the Description page of Project Settings.
#include "ProtobufFileReader.h"
#include "CielimLoggingMacros.h"
#include <google/protobuf/util/delimited_message_util.h>
#include <google/protobuf/io/zero_copy_stream_impl.h>
#include <string>

ProtobufFileReader::ProtobufFileReader(const std::string Filename) : SimulationDataSource(Filename)
{
    // Verify that the version of the library that we linked against is
    // compatible with the version of the headers we compiled against.
    GOOGLE_PROTOBUF_VERIFY_VERSION;

    // Read the existing VizMessage file
    const FString ContentDir = FPaths::ProjectDir(); 
    const std::string Filepath = std::string(TCHAR_TO_UTF8(*ContentDir)) + "/Content/FlybyData/bin/" + Filename;
    this->Input.open(Filepath, std::ios::in | std::ios::binary);

    if (!this->Input) 
    {
        UE_LOG(LogCielim, Warning, TEXT("Failed to open %hs"), Filepath.c_str());
    }

    this->Eof = false;
    this->RawInput = std::make_unique<google::protobuf::io::IstreamInputStream>(&this->Input);
    this->CodedInput = std::make_unique<google::protobuf::io::CodedInputStream>(this->RawInput.get());
}

ProtobufFileReader::~ProtobufFileReader()
{
    // Optional:  Delete all global objects allocated by libprotobuf.
    google::protobuf::ShutdownProtobufLibrary();
    UE_LOG(LogCielim, Warning, TEXT("Protobuf Shutdown Success"));
}

/**
 * Parses data from input stream and returns vizmessage object
 *   
 */
cielimMessage::CielimMessage& ProtobufFileReader::GetNextSimulationData()
{
    cielimMessage::CielimMessage TempMessage;
    google::protobuf::util::ParseDelimitedFromCodedStream(&TempMessage, this->CodedInput.get(), &this->Eof);
    if (TempMessage.ByteSizeLong() != 0) {
        this->CielimMessage.Clear();
        this->CielimMessage = TempMessage;
    }
    return this->CielimMessage;
}
