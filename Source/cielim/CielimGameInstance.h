#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "zmq.hpp"

#include "SceneManager.h"
#include "Router.h"

#include "CielimGameInstance.generated.h"

UCLASS(Blueprintable)
class CIELIM_API UCielimGameInstance : public UGameInstance
{
    GENERATED_BODY()

public:
    //UFUNCTION(BlueprintCallable, Category = "Scene Manager")
    USceneManager* GetSceneManager() const { return SceneManager; }

protected:
    virtual void Init() override;
    virtual void Shutdown() override;

private:
    UPROPERTY()
    USceneManager* SceneManager;

	CielimCircularQueue MultiThreadQueue;

    zmq::context_t Context;
    FRouter* Router;
};
