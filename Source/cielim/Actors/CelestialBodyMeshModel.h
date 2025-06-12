#pragma once

#include <array>

#include "CoreMinimal.h"

#include "../Protobuf/cielimMessage.pb.h"

class CelestialBodyMeshModel
{
public:
	static CelestialBodyMeshModel FromProtobuf(const cielimMessage::MeshModel& Model);

	FString ShapeModel;
    double PerlinNoiseStdDeviation{};  //[-] Standard deviation of the perlin noise to apply (none by default)
    double ProceduralRocks{};  //[-] Parameter to generate procedural rocks on the base mesh (none by default)
    FString BrdfModel; // [string] Name of the BRDF model to apply (Lambertian by default)
    std::array<double, 12> ReflectanceParameters;  //[-] Parameter to apply to BRDF
    double MeanRadius{}; // [m] Length of the mean asteroid radius
    FVector3d PrincipalAxisDistortion{1.0, 1.0, 1.0}; // [%] Length distortions to apply to principal axes (none by default)
	FRotator InertialToBody=FRotator::ZeroRotator; // Attitude of mesh relative to inertial
};
