#include "CielimImageUtilities.h"
#include "ImageUtils.h"

#include <OpenCV/PreOpenCVHeaders.h>
#include "opencv2/imgproc.hpp"
#include <OpenCV/PostOpenCVHeaders.h>

namespace CielimImageUtilities
{
	cv::Mat FImageToOpenCVMat(const FImage& Image)
	{
	    const TArrayView64<const FColor>& PixelData = Image.AsBGRA8();
	    cv::Mat OpenCVMat(Image.GetHeight(), Image.GetWidth(), CV_8UC4, (void*)PixelData.GetData());
	    return OpenCVMat;
	}

	std::optional<FVector2d> ComputeWeightedCenterOfBrightness(const FImage& Image, double Threshold)
	{
		uint32_t WeightSum = 0;
		std::optional<FVector2D> Coordinates = std::nullopt; // Default the case where the image has no brightness
		cv::Mat GrayImage;
		cv::cvtColor(FImageToOpenCVMat(Image), GrayImage, cv::COLOR_BGR2GRAY);
		cv::threshold(GrayImage, GrayImage, Threshold, 255, cv::THRESH_BINARY);

	    // Compute the center of brightness
	    if (const cv::Moments Moments = cv::moments(GrayImage, true); Moments.m00 != 0) {
	        Coordinates.emplace(Moments.m10 / Moments.m00, Moments.m01 / Moments.m00);
	    }

		return Coordinates;
	}

	TArray64<uint8> FImageToPNG(const FImage& Image)
	{
	    TArray64<uint8> PNGImageData;
		verify(FImageUtils::CompressImage(PNGImageData, TEXT("PNG"), Image));
	    return PNGImageData;
	}
}
