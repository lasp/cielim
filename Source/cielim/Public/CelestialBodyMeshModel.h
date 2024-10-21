#pragma once

#include "CoreMinimal.h"
#include "cielimMessage.pb.h"


class CelestialBodyMeshModel
{
public:
	static CelestialBodyMeshModel FromProtobuf(const cielimMessage::CelestialModel& Model);

	FString ShapeModel;
    double PerlinNoiseStdDeviation;  //[-] Standard deviation of the perlin noise to apply (none by default)
    double ProceduralRocks;  //[-] Parameter to generate procedural rocks on the base mesh (none by default)
    FString BrdfModel; // [string] Name of the BRDF model to apply (Lambertian by default)
    std::pair<double, double> ReflectanceParameters;  //[-] Parameter to apply to BRDF
    double MeanRadius; // [m] Length of the mean asteroid radius
    std::pair<double, double> PrincipalAxisDistortion; // [%] Length distortions to apply to principal axes (none by default)
};
