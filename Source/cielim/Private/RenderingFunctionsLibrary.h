#pragma once

#include <OpenCV/PreOpenCVHeaders.h>
#include <opencv2/core.hpp>
#include "opencv2/imgproc.hpp"
#include <OpenCV/opencv/modules/imgcodecs/include/opencv2/imgcodecs.hpp>
#include <OpenCV/PostOpenCVHeaders.h>

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

private:
	static int Clamp(float k, int UpperBound, int LowerBound)
	{
		if(k > UpperBound) return UpperBound;
		else if(k < LowerBound)return  LowerBound;
		else return static_cast<int>(FMath::Floor(k));
	}

public:
	
	static void ApplyPSF_Gaussian(cv::Mat& Image, int32 KernelHeight, int32 KernelWidth, double SigmaX, double SigmaY);
	
	static void ApplyCosmicRays(cv::Mat& Image, int nCosmicRays, float AvgLength, float AvgWidth);
	
	static void ApplyReadNoise(cv::Mat& Image, float ReadNoiseSigma, float SystemGain);
	
	static void ApplySignalGain(cv::Mat& Image, float ImageGain, float DesiredGain);
	
	static void ApplyDarkCurrentNoise(cv::Mat& Image, double MaxSigma, double MinSigma, FVector SunPosition, FVector SpacecraftPosition, FVector SpacecraftDirection);
	
	static void ApplyQE(cv::Mat& Image, float QERed, float QEGreen, float QEBlue);
};
