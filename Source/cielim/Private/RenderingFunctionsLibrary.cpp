#include "RenderingFunctionsLibrary.h"
#include "CielimLoggingMacros.h"
#include <OpenCV/PreOpenCVHeaders.h>
#include <opencv2/core.hpp>
#include "opencv2/imgproc.hpp"
#include <OpenCV/opencv/modules/imgcodecs/include/opencv2/imgcodecs.hpp>
#include <OpenCV/PostOpenCVHeaders.h>

#include <filesystem>

URenderingFunctionsLibrary::URenderingFunctionsLibrary(const FObjectInitializer& ObjectInitializer)
{
	
}

void URenderingFunctionsLibrary::ApplyPSF_Gaussian(TArray<uint8>& ImageData, int32 KernelHeight, int32 KernelWidth, double SigmaX, double SigmaY)
{
	//NOTE: both dimensions of KernelSize must be odd
	
	//Read Image
	cv::Mat Image = cv::imdecode(cv::Mat(1, ImageData.Num(), CV_8UC1, ImageData.GetData()), cv::IMREAD_UNCHANGED);

	if (Image.empty())
	{
		UE_LOG(LogCielim, Error, TEXT("ImageData is Empty!"))
		return;
	}
	
	cv::Mat ResultImage;

	//Get kernel size information into a nice format
	cv::Size KernelSize = cv::Size(KernelHeight, KernelWidth);
	
	cv::GaussianBlur(Image, ResultImage, KernelSize, SigmaX, SigmaY);

	//Save image
	FString ResultFilepath = FPaths::ProjectDir();
	ResultFilepath.Append("Result_Images/");
	ResultFilepath.Append("PSF.jpg");
	
	std::string ResultFilepath_String = TCHAR_TO_UTF8(*ResultFilepath);
	cv::imwrite(ResultFilepath_String, ResultImage);

	// Encode corrupted image as png
    std::vector<uint8> EncodedData;
	cv::imencode(".png", ResultImage, EncodedData);

	// Override ImageData
	ImageData.SetNumUninitialized(EncodedData.size());
	FMemory::Memcpy(ImageData.GetData(), EncodedData.data(), EncodedData.size());
}

void URenderingFunctionsLibrary::ApplyCosmicRays()
{
	//Do Not Call
	throw std::logic_error("Function not yet implemented");
}

void URenderingFunctionsLibrary::ApplyReadNoise(TArray<uint8>& ImageData, float ReadNoiseSigma, float SystemGain)
{
	//Protect Against 0 Sigma
	if(ReadNoiseSigma == 0)
	{
		return;
	}
	
	//Read Image
	cv::Mat Image = cv::imdecode(cv::Mat(1, ImageData.Num(), CV_8UC1, ImageData.GetData()), cv::IMREAD_UNCHANGED);

	if (Image.empty())
	{
		UE_LOG(LogCielim, Error, TEXT("ImageData is Empty!"))
		return;
	}
	
	//Init and create noise matrix
	cv::Mat GaussianNoise = cv::Mat(Image.rows, Image.cols, Image.type());
	cv::randn(GaussianNoise, 0, ReadNoiseSigma);

	//Init Resulting image
	cv::Mat ResultImage = cv::Mat(Image.rows, Image.cols, Image.type());

	//Apply Noise
	ResultImage = Image + (SystemGain * GaussianNoise);

	//Clamp values to [0,255]
	//Separate color channels
	std::array<cv::Mat, 4> DifferentColorChannels;
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

	// Encode corrupted image as png
    std::vector<uint8> EncodedData;
	cv::imencode(".png", ResultImage, EncodedData);

	// Override ImageData
	ImageData.SetNumUninitialized(EncodedData.size());
	FMemory::Memcpy(ImageData.GetData(), EncodedData.data(), EncodedData.size());
}

void URenderingFunctionsLibrary::ApplySignalGain(TArray<uint8>& ImageData, float ImageGain, float DesiredGain)
{
	//Read Image
	cv::Mat Image = cv::imdecode(cv::Mat(1, ImageData.Num(), CV_8UC1, ImageData.GetData()), cv::IMREAD_UNCHANGED);

	if (Image.empty())
	{
		UE_LOG(LogCielim, Error, TEXT("ImageData is Empty!"))
		return;
	}

	Image = Image * (1 / ImageGain);

	//Init Resulting image
	cv::Mat ResultImage = cv::Mat(Image.rows, Image.cols, Image.type());

	ResultImage = Image * DesiredGain;

	//Clamp values to [0,255]
	//Separate color channels
	std::array<cv::Mat, 4> DifferentColorChannels;
	cv::split(ResultImage, DifferentColorChannels);

	//Init LowerBound and UpperBound matrices
	cv::Mat LowerBoundMatrix = cv::Mat::zeros(Image.rows, Image.cols, DifferentColorChannels[0].type());
	cv::Mat UpperBoundMatrix = cv::Mat::ones(Image.rows, Image.cols, DifferentColorChannels[0].type()) * 255;

	//Clamp
	for(int ColorChannel = 0; ColorChannel < 3; ColorChannel++)
	{
		cv::min(cv::max(DifferentColorChannels[ColorChannel], LowerBoundMatrix), UpperBoundMatrix, DifferentColorChannels[ColorChannel]);
	}

	//Merge back into a color image
	cv::merge(DifferentColorChannels, ResultImage);

	//Save image
	FString ResultFilepath = FPaths::ProjectDir();
	ResultFilepath.Append("Result_Images/");
	ResultFilepath.Append("SignalGain.jpg");
	
	std::string ResultFilepath_String = TCHAR_TO_UTF8(*ResultFilepath);
	cv::imwrite(ResultFilepath_String, ResultImage);

	// Encode corrupted image as png
    std::vector<uint8> EncodedData;
	cv::imencode(".png", ResultImage, EncodedData);

	// Override ImageData
	ImageData.SetNumUninitialized(EncodedData.size());
	FMemory::Memcpy(ImageData.GetData(), EncodedData.data(), EncodedData.size());
}

void URenderingFunctionsLibrary::ApplyDarkCurrentNoise(TArray<uint8>& ImageData, double MaxSigma, double MinSigma, FVector SunPosition, FVector SpacecraftPosition, FVector SpacecraftDirection)
{
	//Protect against 0 MaxSigma
	if(MaxSigma == 0)
	{
		return;
	}

	//Protect against MaxSigma < Min Sigma
	if(MaxSigma < MinSigma)
	{
		return;
	}
	
	//Read Image
	cv::Mat Image = cv::imdecode(cv::Mat(1, ImageData.Num(), CV_8UC1, ImageData.GetData()), cv::IMREAD_UNCHANGED);

	if (Image.empty())
	{
		UE_LOG(LogCielim, Error, TEXT("ImageData is Empty!"))
		return;
	}

	//Init Resulting image
	cv::Mat ResultImage = cv::Mat(Image.rows, Image.cols, Image.type());

	//Calculate Influence of Sun on noise
	FVector DirectionVector = SunPosition - SpacecraftPosition;
	DirectionVector.Normalize();
	double DirectionDotProduct = SpacecraftDirection.Dot(DirectionVector);
	DirectionDotProduct = (DirectionDotProduct + 1.0) / 2.0;

	//Calculate noise
	double Sigma =  DirectionDotProduct * (MaxSigma - MinSigma) + MinSigma;

	//Print Sigma
	UE_LOG(LogCielim, Warning, TEXT("Sigma: %s"), *FString::SanitizeFloat(Sigma))
	
	//If sigma == 0, return original image, no noise added
	if( Sigma < 0 )
	{
		//No noise added
		ResultImage = Image;
		
		//Save image
		FString ResultFilepath = FPaths::ProjectDir();
		ResultFilepath.Append("Result_Images/");
		ResultFilepath.Append("DarkCurrentNoise.jpg");
	
		std::string ResultFilepath_String = TCHAR_TO_UTF8(*ResultFilepath);
		cv::imwrite(ResultFilepath_String, ResultImage);
	
		return;
	}
	
	//Init and create noise matrix
	cv::Mat GaussianNoise = cv::Mat::zeros(Image.rows, Image.cols, Image.type());
	cv::randn(GaussianNoise, 0, Sigma);

	//Apply Noise
	ResultImage = Image + GaussianNoise;

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
		cv::min(cv::max(DifferentColorChannels[ColorChannel],LowerBoundMatrix), UpperBoundMatrix, DifferentColorChannels[ColorChannel]);
	}

	//Merge back into a color image
	cv::merge(DifferentColorChannels, ResultImage);

	//Save image
	FString ResultFilepath = FPaths::ProjectDir();
	ResultFilepath.Append("Result_Images/");
	ResultFilepath.Append("DarkCurrentNoise.jpg");
	
	std::string ResultFilepath_String = TCHAR_TO_UTF8(*ResultFilepath);
	cv::imwrite(ResultFilepath_String, ResultImage);

	// Encode corrupted image as png
    std::vector<uint8> EncodedData;
	cv::imencode(".png", ResultImage, EncodedData);

	// Override ImageData
	ImageData.SetNumUninitialized(EncodedData.size());
	FMemory::Memcpy(ImageData.GetData(), EncodedData.data(), EncodedData.size());
}

void URenderingFunctionsLibrary::ApplyQE(TArray<uint8>& ImageData, float QERed, float QEGreen, float QEBlue)
{
	FVector3d QE;

	QE[0] = QERed;
	QE[1] = QEGreen;
	QE[2] = QEBlue;
	
	//Read Image
	cv::Mat Image = cv::imdecode(cv::Mat(1, ImageData.Num(), CV_8UC1, ImageData.GetData()), cv::IMREAD_UNCHANGED);

	if (Image.empty())
	{
		UE_LOG(LogCielim, Error, TEXT("ImageData is Empty!"))
		return;
	}
	
	//Init Result Image
	cv::Mat ResultImage = cv::Mat::zeros(Image.rows, Image.cols, Image.type());

	//Loop Through Every Pixel, Apply QE
	for(int row=0; row < Image.rows; row++)
	{
		for(int col=0; col < Image.cols; col++)
		{
			
			cv::Vec3b NewPixel;
			
			for (int ColorChannel = 0; ColorChannel < 3; ColorChannel++)
			{
				NewPixel[ColorChannel] = static_cast<uchar>(Image.at<cv::Vec3b>(row, col)[ColorChannel] * QE[ColorChannel]);
			}
			
			ResultImage.at<cv::Vec3b>(row, col) = NewPixel;
			
		}
	}
	
	//Save image
	FString ResultFilepath = FPaths::ProjectDir();
	ResultFilepath.Append("Result_Images/");
	ResultFilepath.Append("QE.jpg");
	
	std::string ResultFilepath_String = TCHAR_TO_UTF8(*ResultFilepath);
	cv::imwrite(ResultFilepath_String, ResultImage);

	// Encode corrupted image as png
    std::vector<uint8> EncodedData;
	cv::imencode(".png", ResultImage, EncodedData);

	// Override ImageData
	ImageData.SetNumUninitialized(EncodedData.size());
	FMemory::Memcpy(ImageData.GetData(), EncodedData.data(), EncodedData.size());
}
