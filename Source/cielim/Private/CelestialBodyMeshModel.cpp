#include "CelestialBodyMeshModel.h"


CelestialBodyMeshModel CelestialBodyMeshModel::FromProtobuf(const cielimMessage::MeshModel& Model)
{
	CelestialBodyMeshModel MeshModel = {};
	MeshModel.ShapeModel = FString(Model.shapemodel().c_str());
	MeshModel.PerlinNoiseStdDeviation = Model.perlinnoisestddeviation();
	MeshModel.ProceduralRocks = Model.proceduralrocks();
	MeshModel.BrdfModel = FString(Model.brdfmodel().c_str());
	if (Model.reflectanceparameters().size() == 12)
	{
		MeshModel.ReflectanceParameters = {Model.reflectanceparameters()[0],
			Model.reflectanceparameters()[1],
			Model.reflectanceparameters()[2],
			Model.reflectanceparameters()[3],
			Model.reflectanceparameters()[4],
			Model.reflectanceparameters()[5],
			Model.reflectanceparameters()[6],
			Model.reflectanceparameters()[7],
			Model.reflectanceparameters()[8],
			Model.reflectanceparameters()[9],
			Model.reflectanceparameters()[10],
			Model.reflectanceparameters()[11]};
	}
	MeshModel.MeanRadius = Model.meanradius();
	if (Model.principalaxisdistortion().size() == 2)
	{
		MeshModel.PrincipalAxisDistortion = {Model.principalaxisdistortion()[0], Model.principalaxisdistortion()[1]};
	}
	return MeshModel;
}
