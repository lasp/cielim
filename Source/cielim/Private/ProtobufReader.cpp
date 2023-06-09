// Fill out your copyright notice in the Description page of Project Settings.
#include <iostream>
#include <fstream>

#include "ProtobufReader.h"

ProtobufReader::ProtobufReader(std::string filename)
{
    // Verify that the version of the library that we linked against is
    // compatible with the version of the headers we compiled against.
    GOOGLE_PROTOBUF_VERIFY_VERSION;

    // Read the existing vizmessage file
    FString ContentDir = FPaths::ProjectDir(); 
    std::string filepath = std::string(TCHAR_TO_UTF8(*ContentDir)) + "/Content/FlybyData/bin/" + filename;
    this->input.open(filepath, std::ios::in | std::ios::binary);

    if (!this->input) 
    {
        // Print error message
        UE_LOG(LogTemp, Warning, TEXT("Failed to open %hs"), filepath.c_str());
    }

    this->eof = false;
    this->raw_input = new google::protobuf::io::IstreamInputStream(&this->input);
    this->coded_input = new google::protobuf::io::CodedInputStream(raw_input);
}

ProtobufReader::~ProtobufReader()
{
    // Optional:  Delete all global objects allocated by libprotobuf.
    google::protobuf::ShutdownProtobufLibrary();
    UE_LOG(LogTemp, Warning, TEXT("Protobuf Shutdown Success"));

    delete this->raw_input;
    delete this->coded_input;
}

/**
 * Parses data from input stream and returns vizmessage object
 *   
 */
vizProtobufferMessage::VizMessage& ProtobufReader::ReadInputData()
{
    vizProtobufferMessage::VizMessage tempMessage;
    google::protobuf::util::ParseDelimitedFromCodedStream(&tempMessage, coded_input, &eof);
    if (tempMessage.ByteSizeLong() != 0) {
        this->vizmessage.Clear();
        this->vizmessage = tempMessage;
    }
    return this->vizmessage;
}

