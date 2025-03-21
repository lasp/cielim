#include "CielimGameInstance.h"

#include "CielimLoggingMacros.h"

void UCielimGameInstance::Init()
{
	Super::Init();
	
	// Create the Scene Manager as a child of the GameInstance
	this->SceneManager = NewObject<USceneManager>(this, USceneManager::StaticClass());

	UE_LOG(LogCielim, Display, TEXT("Cielim instance initialized."));
}

void UCielimGameInstance::Shutdown()
{
	// Let GC destroy the SceneManager instance
	this->SceneManager = nullptr;

	UE_LOG(LogCielim, Display, TEXT("Cielim instance shutting down."));
	
	Super::Shutdown();
}


