#pragma once

#include "vizMessage.pb.h"

#include "UCircularQueueData.generated.h"

USTRUCT(BlueprintType) //BlueprintType if want access in BP
struct FCircularQueueData
{
    GENERATED_USTRUCT_BODY()
    
    //This is not UPROPERTY() in the circular queue
    // so do not store UE Actor or UE Object pointers in this struct!
    // UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=CielimCode)
    vizProtobufferMessage::VizMessage Message;
};
