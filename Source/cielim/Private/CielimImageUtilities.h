#include <OpenCV/PreOpenCVHeaders.h>
#include <opencv2/core.hpp>
#include <OpenCV/PostOpenCVHeaders.h>

namespace CielimImageUtilities
{
	cv::Mat FImageToOpenCVMat(const FImage& Image);
	std::optional<FVector2d> ComputeWeightedCenterOfBrightness(const FImage& Image, double Threshold);
	TArray64<uint8> FImageToPNG(const FImage& Image);
}
