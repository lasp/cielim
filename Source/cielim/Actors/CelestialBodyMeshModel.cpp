//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of FCelestialBodyMeshModel.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CelestialBodyMeshModel.h"

#include "../Utilities/Math/KinematicsUtilities.h"

FCelestialBodyMeshModel FCelestialBodyMeshModel::FromProtobuf(const cielimMessage::MeshModel &Model)
{
	FCelestialBodyMeshModel MeshModel = {};

	MeshModel.ShapeModel = FString(Model.shapemodel().c_str());

	if (Model.has_refmodel())
	{
		const cielimMessage::ReflectanceModel &RefModel = Model.refmodel();

		MeshModel.BrdfModel = FString(RefModel.brdfmodel().c_str());

		if (Model.refmodel().reflectanceparameters().size() == 12)
		{
			MeshModel.ReflectanceParameters = {
				RefModel.reflectanceparameters()[0],  RefModel.reflectanceparameters()[1],
				RefModel.reflectanceparameters()[2],  RefModel.reflectanceparameters()[3],
				RefModel.reflectanceparameters()[4],  RefModel.reflectanceparameters()[5],
				RefModel.reflectanceparameters()[6],  RefModel.reflectanceparameters()[7],
				RefModel.reflectanceparameters()[8],  RefModel.reflectanceparameters()[9],
				RefModel.reflectanceparameters()[10], RefModel.reflectanceparameters()[11]};
		}
	}

	if (Model.has_perlinnoise())
	{
		MeshModel.HasPerlinNoise = true;
		MeshModel.Octaves = Model.perlinnoise().octavecount();
		MeshModel.BaseAmplitude = Model.perlinnoise().baseamplitude();
		MeshModel.BaseFrequency = Model.perlinnoise().basefrequency();
		MeshModel.Persistence = Model.perlinnoise().persistence();
	}

	MeshModel.ProceduralRocks = Model.proceduralrocks();
	MeshModel.MeanRadius = Model.meanradius();
	MeshModel.GeometricAlbedo = Model.geometricalbedo();

	if (Model.principalaxisdistortion().size() == 3)
	{
		MeshModel.PrincipalAxisDistortion = {Model.principalaxisdistortion()[0], Model.principalaxisdistortion()[1],
											 Model.principalaxisdistortion()[2]};
	}

	if (Model.inertialtobodymrp().size() == 3)
	{
		const FVector3d SigmaBN =
			FVector3d(Model.inertialtobodymrp()[0], Model.inertialtobodymrp()[1], Model.inertialtobodymrp()[2]);
		const FQuat QuatBN = MRPtoQuaternion(SigmaBN);
		MeshModel.InertialToBody = FRotator(RightQuat2LeftQuat(QuatBN));
	}

	return MeshModel;
}
