// Fill out your copyright notice in the Description page of Project Settings.
#include "ProtobufFileReader.h"
#include "CielimLoggingMacros.h"
#include <google/protobuf/util/delimited_message_util.h>
#include <google/protobuf/io/zero_copy_stream_impl.h>
#include <string>

ProtobufFileReader::ProtobufFileReader(std::string filename) : SimulationDataSource(filename)
{
    // Verify that the version of the library that we linked against is
    // compatible with the version of the headers we compiled against.
    GOOGLE_PROTOBUF_VERIFY_VERSION;

    // Read the existing vizmessage file
    const FString ContentDir = FPaths::ProjectDir(); 
    const std::string Filepath = std::string(TCHAR_TO_UTF8(*ContentDir)) + "/Content/FlybyData/bin/" + filename;
    this->input.open(Filepath, std::ios::in | std::ios::binary);

    if (!this->input) 
    {
        // Print error message
        UE_LOG(LogCielim, Warning, TEXT("Failed to open %hs"), Filepath.c_str());
    }

    this->eof = false;
    this->raw_input = new google::protobuf::io::IstreamInputStream(&this->input);
    this->coded_input = new google::protobuf::io::CodedInputStream(raw_input);
}

ProtobufFileReader::~ProtobufFileReader()
{
    // Optional:  Delete all global objects allocated by libprotobuf.
    google::protobuf::ShutdownProtobufLibrary();
    UE_LOG(LogCielim, Warning, TEXT("Protobuf Shutdown Success"));

    delete this->raw_input;
    delete this->coded_input;
}

/**
 * Parses data from input stream and returns vizmessage object
 *   
 */
vizProtobufferMessage::VizMessage& ProtobufFileReader::GetNextSimulationData()
{
    vizProtobufferMessage::VizMessage tempMessage;
    google::protobuf::util::ParseDelimitedFromCodedStream(&tempMessage, coded_input, &eof);
    if (tempMessage.ByteSizeLong() != 0) {
        this->vizmessage.Clear();
        this->vizmessage = tempMessage;
    }
    return this->vizmessage;
}

