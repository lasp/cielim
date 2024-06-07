#pragma once

#include "CoreMinimal.h"
#include "Math/Vector.h"
#include "Engine/World.h"
#include "Kismet/BlueprintFunctionLibrary.h"

#include <OpenCV/PreOpenCVHeaders.h>
#include "OpenCV/opencv-4.5.5/modules/imgcodecs/include/opencv2/imgcodecs.hpp"
#include <OpenCV/PostOpenCVHeaders.h>

#include "RenderingFunctionsLibrary.generated.h"

UCLASS()
class  CIELIM_API URenderingFunctionsLibrary :
	public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
	
	URenderingFunctionsLibrary(const FObjectInitializer& ObjectInitializer);
	
	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static void ApplyPSF_Gaussian();

	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	FString ApplyCosmicRays(FString Filepath, int nCosmicRays, float AvgLength, float AvgWidth);

	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static void ApplyReadNoise();

	int Clamp(float k, int UpperBound, int LowerBound);
};



