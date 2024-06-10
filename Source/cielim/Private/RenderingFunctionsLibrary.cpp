
#include "RenderingFunctionsLibrary.h"

#include <OpenCV/PreOpenCVHeaders.h>
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <OpenCV/opencv-4.5.5/modules/imgcodecs/include/opencv2/imgcodecs.hpp>
#include <OpenCV/PostOpenCVHeaders.h>

URenderingFunctionsLibrary::URenderingFunctionsLibrary(const FObjectInitializer& ObjectInitializer)
{

}

void URenderingFunctionsLibrary::ApplyPSF_Gaussian()

{
	
}

FString URenderingFunctionsLibrary::ApplyCosmicRays(FString Filepath, int nCosmicRays, float AvgLength, float AvgWidth)
{
	//TODO: Add varying width to lines
	//TODO: Make it so that lines w/ start and end points don't get clipped to image sides
	
	//Read Image
	FString Filepath_Absolute = IFileManager::Get().ConvertToAbsolutePathForExternalAppForRead(*Filepath);
	std::string Filepath_Absolute_String = TCHAR_TO_UTF8(*Filepath_Absolute);
	cv::Mat Image = cv::imread(Filepath_Absolute_String);

	for(int i=0; i < nCosmicRays; i++)
	{
		//calculate starting point (Uniform)
		int XStartCoord = FMath::RandRange(0, Image.cols);
		int YStartCoord = FMath::RandRange(0, Image.rows);

		cv::Point StartPoint {XStartCoord, YStartCoord};

		//calculate angle (Uniform)
		float Angle = FMath::FRandRange(0, 359.9);

		//calculate length (Exponential)
		float Uniform0 = FMath::FRandRange(0.0, 1.0);
		float Length = -1 * AvgLength * FMath::Loge(Uniform0);

		//calculate ending point
		int XStopCoord = XStartCoord + static_cast<int>(Length * FMath::Cos(Angle));
		int YStopCoord = YStartCoord + static_cast<int>(Length * FMath::Sin(Angle));

		XStopCoord = Clamp(XStopCoord, Image.cols, 0);
		YStopCoord = Clamp(YStopCoord, Image.rows, 0);

		cv::Point StopPoint {XStopCoord, YStopCoord};

		//calculate width (Uniform)
		float Uniform1 = FMath::FRandRange(0.0, 1.0);
		int Width = static_cast<int>(-1 * AvgWidth * FMath::Loge(Uniform1));

		//Draw the line!
		cv::line(Image, StartPoint, StopPoint, cv::Vec3b{255,255,255}, 1, cv::LINE_4);
	}
	
	//Save image
	FString ResultFilepath = FPaths::ProjectDir();
	ResultFilepath.Append("Result_Images/");
	ResultFilepath.Append("CosmicRays.jpg");
	
	std::string ResultFilepath_String = TCHAR_TO_UTF8(*ResultFilepath);
	cv::imwrite(ResultFilepath_String, Image);
	
	return ResultFilepath;
}

void URenderingFunctionsLibrary::ApplyReadNoise()
{
	
}


int URenderingFunctionsLibrary::Clamp(float k, int UpperBound, int LowerBound)
{
	if(k > UpperBound)
	{
		return UpperBound;
	}
	else if(k < LowerBound)
	{
		return LowerBound;
	}
	else
	{
		return static_cast<int>(FMath::Floor(k));
	}
}