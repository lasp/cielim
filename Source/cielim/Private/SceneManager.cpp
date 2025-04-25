//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of USceneManager.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "SceneManager.h"

#include "Kismet/GameplayStatics.h"

#include "CielimLoggingMacros.h"

void USceneManager::Init(zmq::context_t &ContextPtr, CielimCircularQueue &CircularQueue)
{
	this->QueueBridge = NewObject<UQueueBridge>(this, UQueueBridge::StaticClass());
	this->QueueBridge->Connect(ContextPtr, CircularQueue);
}

bool USceneManager::IsTickable() const
{
	// Should tick if request queue is not empty
	if (QueueBridge != nullptr)
		return QueueBridge->NumQueueInbound() != 0;

	return false;
}

void USceneManager::Tick(float DeltaTime)
{
	// Retry scene search
	if (!this->Scene)
		this->Scene = Cast<ASimulationDataSourceActor>(
			UGameplayStatics::GetActorOfClass(this, ASimulationDataSourceActor::StaticClass()));

	const TOptional<FCircularQueueData> QueueData = this->QueueBridge->GetQueueData();

	if (!QueueData.IsSet())
		return;

	FCircularQueueData ReturnData;

	ReturnData.ID = QueueData.GetValue().ID;
	ReturnData.bUseDelim = QueueData.GetValue().bUseDelim;

	this->Scene->ParseCommand(QueueData.GetValue(), ReturnData);
	this->Scene->UpdateScene();

	// Request Image is the only command that currently requests return data
	// instead of an instant "OK" message currently.
	if (ReturnData.query == CommandType::REQUEST_IMAGE)
	{
		QueueBridge->PutQueueData(ReturnData);
	}
}

TStatId USceneManager::GetStatId() const { RETURN_QUICK_DECLARE_CYCLE_STAT(USceneManager, STATGROUP_Tickables); }
