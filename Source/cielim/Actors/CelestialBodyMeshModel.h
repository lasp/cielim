//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FCelestialBodyMeshModel actor class which serves as a wrapper for the protobuf
//          MeshModel parameter.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include <array>

#include "CoreMinimal.h"

#include "../Protobuf/cielimMessage.pb.h"

class FCelestialBodyMeshModel
{
public:
	static FCelestialBodyMeshModel FromProtobuf(const cielimMessage::MeshModel &Model);

	FString ShapeModel; // The name of the mesh model to use in the scene.
	FString BrdfModel; // Name of the BRDF model to apply

	std::array<double, 12> ReflectanceParameters; //[-] Parameter to apply to BRDF

	bool HasPerlinNoise{false}; //[-] Whether the perlin noise parameters are defined
	int Octaves{0}; //[-] Number of octaves of the perlin noise
	double BaseAmplitude{0.0f}; //[-] Base amplitude of the perlin noise
	double BaseFrequency{0.0f}; //[-] Base frequency of the perlin noise
	double Persistence{0.0f}; //[-] Persistence of the perlin noise
	double ProceduralRocks{0.0f}; //[-] Parameter to generate procedural rocks on the base mesh
	double MeanRadius{0.0f}; //[m] Length of the mean asteroid radius

	FVector3d PrincipalAxisDistortion{1.0, 1.0, 1.0}; //[%] Length distortions to apply to principal axes
	FRotator InertialToBody = FRotator::ZeroRotator; // Attitude of mesh relative to inertial
};
