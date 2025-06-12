//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of UCielimGameInstance.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CielimGameInstance.h"

#include "Utilities/Logging/CielimLoggingMacros.h"

void UCielimGameInstance::Init()
{
	Super::Init();

	this->Context = zmq::context_t(1);

	FString CommAddress;

	// Check for command line parameter for directComm and store in CommAddress

	if (FParse::Value(FCommandLine::Get(), TEXT("directComm"), CommAddress))
	{
		UE_LOG(LogCielim, Display, TEXT("Parsed command line parameter (directComm) : %s"), *CommAddress);
	}
	else
	{
		UE_LOG(LogCielim, Display, TEXT("No command line parameter found; using default localhost."))
		CommAddress = "tcp://localhost:5556";
	}

	this->Router = new FRouter(Context, std::string(TCHAR_TO_UTF8(*CommAddress)), MultiThreadQueue);

	// Get pointer to scene manager subsystem
	this->SceneManager = GetSubsystem<USceneManager>();
	check(this->SceneManager);

	this->SceneManager->Init(Context, MultiThreadQueue);

	int Major;
	int Minor;
	int Patch;
	zmq::version(&Major, &Minor, &Patch);
	UE_LOG(LogCielim, Display, TEXT("ZeroMQ version: v%d.%d.%d"), Major, Minor, Patch);

	UE_LOG(LogCielim, Display, TEXT("UCielimGameInstance : Cielim instance initialized."));
}

void UCielimGameInstance::Shutdown()
{
	// Let GC destroy the SceneManager instance
	this->SceneManager = nullptr;

	if (this->Router)
	{
		this->Router->Shutdown();
		delete this->Router;
	}

	google::protobuf::ShutdownProtobufLibrary();

	UE_LOG(LogCielim, Display, TEXT("UCielimGameInstance : Cielim instance shutting down."));

	Super::Shutdown();
}
