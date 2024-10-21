#include "CelestialBodyMeshModel.h"


CelestialBodyMeshModel CelestialBodyMeshModel::FromProtobuf(const cielimMessage::CelestialModel& Model)
{
	CelestialBodyMeshModel MeshModel = {};
	MeshModel.ShapeModel = FString(Model.shapemodel().c_str());
	MeshModel.PerlinNoiseStdDeviation = Model.perlinnoisestddeviation();
	MeshModel.ProceduralRocks = Model.proceduralrocks();
	MeshModel.BrdfModel = FString(Model.brdfmodel().c_str());
	if (Model.reflectanceparameters().size() == 2)
	{
		MeshModel.ReflectanceParameters = {Model.reflectanceparameters()[0], Model.reflectanceparameters()[1]};	
	}
	MeshModel.MeanRadius = Model.meanradius();
	if (Model.principalaxisdistortion().size() == 2)
	{
		MeshModel.PrincipalAxisDistortion = {Model.principalaxisdistortion()[0], Model.principalaxisdistortion()[1]};
	}
	return MeshModel;
}
