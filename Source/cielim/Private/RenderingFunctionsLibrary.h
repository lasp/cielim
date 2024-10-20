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

public:
	
	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static void ApplyPSF_Gaussian(TArray<uint8>& ImageData, int32 KernelHeight, int32 KernelWidth, double SigmaX, double SigmaY);
	
	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static void ApplyCosmicRays();

	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static void ApplyReadNoise(TArray<uint8>& ImageData, float ReadNoiseSigma, float SystemGain);

	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static void ApplySignalGain(TArray<uint8>& ImageData, float ImageGain, float DesiredGain);

	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static void ApplyDarkCurrentNoise(TArray<uint8>& ImageData, double MaxSigma, double MinSigma, FVector SunPosition, FVector SpacecraftPosition, FVector SpacecraftDirection);

	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static void ApplyQE(TArray<uint8>& ImageData, float QERed, float QEGreen, float QEBlue);
};
