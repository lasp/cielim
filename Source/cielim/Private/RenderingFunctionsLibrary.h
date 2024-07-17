#pragma once

#include "CoreMinimal.h"
#include "Math/Vector.h"
#include "Engine/World.h"
#include "Kismet/BlueprintFunctionLibrary.h"

#include "RenderingFunctionsLibrary.generated.h"

UCLASS()
class  CIELIM_API URenderingFunctionsLibrary :
	public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
	
	URenderingFunctionsLibrary(const FObjectInitializer& ObjectInitializer);
	
	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static FString ApplyPSF_Gaussian(FString Filepath, int32 KernelHeight, int32 KernelWidth, double SigmaX, double SigmaY);
	
	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static void ApplyCosmicRays();

	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static void ApplyReadNoise();
};
