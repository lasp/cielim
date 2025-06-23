#include "RenderingFunctionsLibrary.h"

#include <random>

// clang-format off
#include "OpenCV/PreOpenCVHeaders.h"
#include "opencv2/imgproc.hpp"
#include "OpenCV/opencv/modules/imgcodecs/include/opencv2/imgcodecs.hpp"
#include "OpenCV/PostOpenCVHeaders.h"
// clang-format on

#include "../Utilities/Logging/CielimLoggingMacros.h"

static std::default_random_engine generator;

URenderingFunctionsLibrary::URenderingFunctionsLibrary(const FObjectInitializer &ObjectInitializer) {}

void URenderingFunctionsLibrary::ApplyPSF_Gaussian(cv::Mat &Image, int32 KernelHeight, int32 KernelWidth, double SigmaX,
												   double SigmaY)
{
	// NOTE: both dimensions of KernelSize must be odd

	// If no blur is applied, we can skip the rest of this
	if (SigmaX == 0.0f || SigmaY == 0.0f)
	{
		return;
	}

	if (Image.empty())
	{
		UE_LOG(LogCielim, Error, TEXT("ImageData is Empty!"))
		return;
	}

	cv::Mat ResultImage;

	// Get kernel size information into a nice format
	cv::Size KernelSize = cv::Size(KernelHeight, KernelWidth);

	cv::GaussianBlur(Image, ResultImage, KernelSize, SigmaX, SigmaY);

	// Override Image
	Image = ResultImage.clone();
}

void URenderingFunctionsLibrary::ApplyCosmicRays(cv::Mat &Image, double cosmicRaysStdDev, float AvgLength,
												 float AvgWidth)
{
	// TODO: Add varying width to lines
	// TODO: Make it so that lines w/ start and end points don't get clipped to image sides

	std::poisson_distribution<int> cosmicRayDistribution(cosmicRaysStdDev);
	int nCosmicRays = cosmicRayDistribution(generator);

	// Skip if no cosmic rays will be applied
	if (nCosmicRays == 0)
	{
		return;
	}

	if (Image.empty())
	{
		UE_LOG(LogCielim, Error, TEXT("ImageData is Empty!"))
		return;
	}

	for (int i = 0; i < nCosmicRays; i++)
	{
		// calculate starting point (Uniform)
		int XStartCoord = FMath::RandRange(0, Image.cols);
		int YStartCoord = FMath::RandRange(0, Image.rows);

		cv::Point StartPoint{XStartCoord, YStartCoord};

		// calculate angle (Uniform)
		float Angle = FMath::FRandRange(0, 359.9);

		// calculate length (Exponential)
		float Uniform0 = FMath::FRandRange(0.0, 1.0);
		float Length = -1 * AvgLength * FMath::Loge(Uniform0);

		// calculate ending point
		int XStopCoord = XStartCoord + static_cast<int>(Length * FMath::Cos(Angle));
		int YStopCoord = YStartCoord + static_cast<int>(Length * FMath::Sin(Angle));

		XStopCoord = Clamp(XStopCoord, Image.cols, 0);
		YStopCoord = Clamp(YStopCoord, Image.rows, 0);

		cv::Point StopPoint{XStopCoord, YStopCoord};

		// calculate width (Uniform)
		float Uniform1 = FMath::FRandRange(0.0, 1.0);
		int Width = static_cast<int>(-1 * AvgWidth * FMath::Loge(Uniform1));

		// Draw the line!
		cv::line(Image, StartPoint, StopPoint, cv::Vec3b{255, 255, 255}, 1, cv::LINE_4);
	}
}

void URenderingFunctionsLibrary::ApplyReadNoise(cv::Mat &Image, float ReadNoiseSigma, float SystemGain)
{
	// Protect Against 0 Sigma
	if (ReadNoiseSigma == 0.0f)
	{
		return;
	}

	if (Image.empty())
	{
		UE_LOG(LogCielim, Error, TEXT("ImageData is Empty!"))
		return;
	}

	// Init and create noise matrix
	cv::Mat GaussianNoise = cv::Mat(Image.rows, Image.cols, Image.type());
	cv::randn(GaussianNoise, 0, ReadNoiseSigma);

	// Init Resulting image
	cv::Mat ResultImage = cv::Mat(Image.rows, Image.cols, Image.type());

	// Apply Noise
	ResultImage = Image + (SystemGain * GaussianNoise);

	// Clamp values to [0,255]
	// Separate color channels
	std::array<cv::Mat, 4> DifferentColorChannels;
	cv::split(ResultImage, DifferentColorChannels);

	// Init LowerBound and UpperBound matrices
	cv::Mat LowerBoundMatrix = cv::Mat::zeros(Image.rows, Image.cols, DifferentColorChannels[0].type());
	cv::Mat UpperBoundMatrix = cv::Mat::ones(Image.rows, Image.cols, DifferentColorChannels[0].type()) * 255;

	// Clamp
	for (int ColorChannel = 0; ColorChannel < 3; ColorChannel++)
	{
		cv::min(cv::max(DifferentColorChannels[ColorChannel], LowerBoundMatrix), UpperBoundMatrix,
				DifferentColorChannels[ColorChannel]);
	}

	// Merge back into a color image
	cv::merge(DifferentColorChannels, ResultImage);

	Image = ResultImage.clone();
}

void URenderingFunctionsLibrary::ApplySignalGain(cv::Mat &Image, float ImageGain, float DesiredGain)
{
	if (DesiredGain == 0.0f)
	{
		return;
	}

	if (Image.empty())
	{
		UE_LOG(LogCielim, Error, TEXT("ImageData is Empty!"))
		return;
	}

	Image = Image * (1 / ImageGain);

	// Init Resulting image
	cv::Mat ResultImage = cv::Mat(Image.rows, Image.cols, Image.type());

	ResultImage = Image * DesiredGain;

	// Clamp values to [0,255]
	// Separate color channels
	std::array<cv::Mat, 4> DifferentColorChannels;
	cv::split(ResultImage, DifferentColorChannels);

	// Init LowerBound and UpperBound matrices
	cv::Mat LowerBoundMatrix = cv::Mat::zeros(Image.rows, Image.cols, DifferentColorChannels[0].type());
	cv::Mat UpperBoundMatrix = cv::Mat::ones(Image.rows, Image.cols, DifferentColorChannels[0].type()) * 255;

	// Clamp
	for (int ColorChannel = 0; ColorChannel < 3; ColorChannel++)
	{
		cv::min(cv::max(DifferentColorChannels[ColorChannel], LowerBoundMatrix), UpperBoundMatrix,
				DifferentColorChannels[ColorChannel]);
	}

	// Merge back into a color image
	cv::merge(DifferentColorChannels, ResultImage);
	Image = ResultImage.clone();
}

void URenderingFunctionsLibrary::ApplyDarkCurrentNoise(cv::Mat &Image, double MaxSigma, double MinSigma,
													   FVector SunPosition, FVector SpacecraftPosition,
													   FVector SpacecraftDirection)
{
	// Protect against 0 MaxSigma
	if (MaxSigma == 0.0f)
	{
		return;
	}

	// Protect against MaxSigma < Min Sigma
	if (MaxSigma < MinSigma)
	{
		return;
	}

	if (Image.empty())
	{
		UE_LOG(LogCielim, Error, TEXT("ImageData is Empty!"))
		return;
	}

	// Init Resulting image
	cv::Mat ResultImage = cv::Mat(Image.rows, Image.cols, Image.type());

	// Calculate Influence of Sun on noise
	FVector DirectionVector = SunPosition - SpacecraftPosition;
	DirectionVector.Normalize();
	double DirectionDotProduct = SpacecraftDirection.Dot(DirectionVector);
	DirectionDotProduct = (DirectionDotProduct + 1.0) / 2.0;

	// Calculate noise
	double Sigma = DirectionDotProduct * (MaxSigma - MinSigma) + MinSigma;

	// Print Sigma
	UE_LOG(LogCielim, Warning, TEXT("Sigma: %s"), *FString::SanitizeFloat(Sigma))

	// If sigma == 0, return original image, no noise added
	if (Sigma < 0)
	{
		// No noise added
		ResultImage = Image;

		// Save image
		FString ResultFilepath = FPaths::ProjectDir();
		ResultFilepath.Append("Result_Images/");
		ResultFilepath.Append("DarkCurrentNoise.jpg");

		std::string ResultFilepath_String = TCHAR_TO_UTF8(*ResultFilepath);
		cv::imwrite(ResultFilepath_String, ResultImage);

		return;
	}

	// Init and create noise matrix
	cv::Mat GaussianNoise = cv::Mat::zeros(Image.rows, Image.cols, Image.type());
	cv::randn(GaussianNoise, 0, Sigma);

	// Apply Noise
	ResultImage = Image + GaussianNoise;

	// Clamp values to [0,255]
	// Separate color channels
	std::vector<cv::Mat> DifferentColorChannels;
	cv::split(ResultImage, DifferentColorChannels);

	// Init LowerBound and UpperBound matrices
	cv::Mat LowerBoundMatrix = cv::Mat::zeros(Image.rows, Image.cols, DifferentColorChannels[0].type());
	cv::Mat UpperBoundMatrix = cv::Mat::ones(Image.rows, Image.cols, DifferentColorChannels[0].type()) * 255;

	// Clamp
	for (int ColorChannel = 0; ColorChannel < 3; ColorChannel++)
	{
		cv::min(cv::max(DifferentColorChannels[ColorChannel], LowerBoundMatrix), UpperBoundMatrix,
				DifferentColorChannels[ColorChannel]);
	}

	// Merge back into a color image
	cv::merge(DifferentColorChannels, ResultImage);
	Image = ResultImage.clone();
}

void URenderingFunctionsLibrary::ApplyQE(cv::Mat &Image, float QERed, float QEGreen, float QEBlue)
{
	FVector3d QE;

	QE[0] = QERed;
	QE[1] = QEGreen;
	QE[2] = QEBlue;

	if (Image.empty())
	{
		UE_LOG(LogCielim, Error, TEXT("ImageData is Empty!"))
		return;
	}

	// Init Result Image
	cv::Mat ResultImage = cv::Mat::zeros(Image.rows, Image.cols, Image.type());

	// Loop Through Every Pixel, Apply QE
	for (int row = 0; row < Image.rows; row++)
	{
		for (int col = 0; col < Image.cols; col++)
		{

			cv::Vec3b NewPixel;

			for (int ColorChannel = 0; ColorChannel < 3; ColorChannel++)
			{
				NewPixel[ColorChannel] =
					static_cast<uchar>(Image.at<cv::Vec3b>(row, col)[ColorChannel] * QE[ColorChannel]);
			}

			ResultImage.at<cv::Vec3b>(row, col) = NewPixel;
		}
	}
	Image = ResultImage.clone();
}
