#pragma once

#include "Commands.h"
#include "UCircularQueueData.generated.h"

USTRUCT(BlueprintType) //BlueprintType if want access in BP
struct FCircularQueueData
{
    GENERATED_USTRUCT_BODY()
    
    //This is not UPROPERTY() in the circular queue
    // so do not store UE Actor or UE Object pointers in this struct!
    // UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=CielimCode)
    std::variant<Ping, SimUpdate, RequestImage, BSKError> Query;
};
