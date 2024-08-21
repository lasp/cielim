#include "ProceduralRocksHelperFunctions.h"


UProceduralRocksHelperFunctions::UProceduralRocksHelperFunctions(const FObjectInitializer& ObjectInitializer)
{
	
}

UStaticMesh* UProceduralRocksHelperFunctions::GetStaticMeshCopy(UStaticMesh* const DesiredMesh)
{
	UStaticMesh* DuplicateMesh = DuplicateObject(DesiredMesh, DesiredMesh->GetOuter());
	return DuplicateMesh;
}