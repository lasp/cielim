//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of USceneManager.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "SceneManager.h"

#include "../Utilities/Logging/CielimLoggingMacros.h"

void USceneManager::Init(zmq::context_t &ContextPtr, CielimCircularQueue &CircularQueue)
{
	this->QueueBridge = NewObject<UQueueBridge>(this, UQueueBridge::StaticClass());
	this->QueueBridge->Connect(ContextPtr, CircularQueue);
}

bool USceneManager::IsTickable() const
{
	// Should tick if request queue is not empty
	if (this->QueueBridge != nullptr)
		return this->QueueBridge->NumQueueInbound() != 0;

	return false;
}

void USceneManager::Tick(float DeltaTime)
{
	const TOptional<FCircularQueueData> QueueData = this->QueueBridge->GetQueueData();

	if (!QueueData.IsSet())
		return;

	const uint8 SceneID = QueueData.GetValue().SceneID;

	if (QueueData.GetValue().query == CommandType::NEW_SCENE)
	{
		USceneData *NewScene = NewObject<USceneData>(this, USceneData::StaticClass());
		NewScene->Init();

		Scenes.Add(SceneID, NewScene);

		UE_LOG(LogCielim, Display, TEXT("SceneManager : New Scene created with ID %d"), SceneID);
	}
	else if (QueueData.GetValue().query == CommandType::REMOVE_SCENE)
	{
		if (USceneData *Scene = *Scenes.Find(SceneID); Scene != nullptr)
		{
			if (ActiveScene == Scene)
				ActiveScene = nullptr;

			Scene->MarkAsGarbage();
			Scenes.Remove(SceneID);

			UE_LOG(LogCielim, Display, TEXT("SceneManager : Scene removed for ID %d"), SceneID);
		}
		else
		{
			UE_LOG(LogCielim, Warning, TEXT("SceneManager : Scene with ID %d couldn't be found for deletion."),
				   SceneID);
		}
	}
	else if (USceneData *Scene = *Scenes.Find(SceneID); Scene != nullptr)
	{
		if (Scene->IsSceneEstablished() && !Scene->IsSunLightOn())
			Scene->ToggleSunLight(true);

		if (ActiveScene != Scene)
		{
			if (ActiveScene != nullptr && ActiveScene->IsSceneEstablished())
				ActiveScene->ToggleSunLight(false);

			ActiveScene = Scene;
		}

		FCircularQueueData ReturnData;

		ReturnData.ID = QueueData.GetValue().ID;
		ReturnData.bUseDelim = QueueData.GetValue().bUseDelim;

		Scene->ParseCommand(QueueData.GetValue(), ReturnData);
		Scene->UpdateScene();

		// Request Image is the only command that currently requests return data
		// instead of an instant "OK" message currently.
		if (ReturnData.query == CommandType::REQUEST_IMAGE)
		{
			this->QueueBridge->PutQueueData(ReturnData);
		}
	}
	else
	{
		UE_LOG(LogCielim, Warning,
			   TEXT("SceneManager : Scene with ID %d couldn't be found for non-registration command."), SceneID);
	}
}

TStatId USceneManager::GetStatId() const { RETURN_QUICK_DECLARE_CYCLE_STAT(USceneManager, STATGROUP_Tickables); }
