
#include "RenderingFunctionsLibrary.h"

#include <OpenCV/PreOpenCVHeaders.h>
#include <opencv2/core.hpp>
#include <OpenCV/opencv-4.5.5/modules/imgcodecs/include/opencv2/imgcodecs.hpp>
#include <OpenCV/PostOpenCVHeaders.h>

URenderingFunctionsLibrary::URenderingFunctionsLibrary(const FObjectInitializer& ObjectInitializer)
{

}

void URenderingFunctionsLibrary::ApplyPSF_Gaussian()

{
	
}

void URenderingFunctionsLibrary::ApplyCosmicRays()
{
	
}

FString URenderingFunctionsLibrary::ApplyReadNoise(FString Filepath, float ReadNoiseSigma, float SystemGain)
{
	//Protect Against 0 Sigma
	if(ReadNoiseSigma == 0)
	{
		return Filepath;
	}
	
	//Read Image
	FString Filepath_Absolute = IFileManager::Get().ConvertToAbsolutePathForExternalAppForRead(*Filepath);
	std::string Filepath_Absolute_String = TCHAR_TO_UTF8(*Filepath_Absolute);
	cv::Mat Image = cv::imread(Filepath_Absolute_String);
	
	//Init and create noise matrix
	cv::Mat GaussianNoise = cv::Mat(Image.rows, Image.cols, Image.type());
	cv::randn(GaussianNoise, 0, ReadNoiseSigma);

	//Init Resulting image
	cv::Mat ResultImage = cv::Mat(Image.rows, Image.cols, Image.type());

	//Apply Noise
	ResultImage = Image + (SystemGain * GaussianNoise);

	//Clamp values to [0,255]
	//Separate color channels
	std::vector<cv::Mat> DifferentColorChannels;
	cv::split(ResultImage, DifferentColorChannels);

	//Init LowerBound and UpperBound matrices
	cv::Mat LowerBoundMatrix = cv::Mat::zeros(Image.rows, Image.cols, DifferentColorChannels[0].type());
	cv::Mat UpperBoundMatrix = cv::Mat::ones(Image.rows, Image.cols, DifferentColorChannels[0].type()) * 255;

	//Clamp
	for(int ColorChannel =0; ColorChannel < 3; ColorChannel++)
	{
		cv::min(cv::max(DifferentColorChannels[ColorChannel], LowerBoundMatrix), UpperBoundMatrix, DifferentColorChannels[ColorChannel]);
	}

	//Merge back into a color image
	cv::merge(DifferentColorChannels, ResultImage);

	//Save image
	FString ResultFilepath = FPaths::ProjectDir();
	ResultFilepath.Append("Result_Images/");
	ResultFilepath.Append("ReadNoise.jpg");
	
	std::string ResultFilepath_String = TCHAR_TO_UTF8(*ResultFilepath);
	cv::imwrite(ResultFilepath_String, ResultImage);
	
	return ResultFilepath;
}