#pragma once

#include "CoreMinimal.h"

#include "ZmqConnection/ZmqMultiThreadActor.h"

#include "SceneManager.generated.h"

UCLASS()
class CIELIM_API USceneManager : public UObject, public FTickableGameObject
{
    GENERATED_BODY()

public:
	USceneManager();
	
	virtual bool IsTickable() const override;
	virtual void Tick(float DeltaTime) override;

};
