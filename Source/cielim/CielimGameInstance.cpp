#include "CielimGameInstance.h"

#include "CielimLoggingMacros.h"

void UCielimGameInstance::Init()
{
	Super::Init();
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

	// Create the Scene Manager as a child of the GameInstance
	this->SceneManager = NewObject<USceneManager>(this, USceneManager::StaticClass());
	this->SceneManager->Init(std::string(TCHAR_TO_UTF8(*CommAddress)));

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

	google::protobuf::ShutdownProtobufLibrary();

	UE_LOG(LogCielim, Display, TEXT("UCielimGameInstance : Cielim instance shutting down."));

	Super::Shutdown();
}
