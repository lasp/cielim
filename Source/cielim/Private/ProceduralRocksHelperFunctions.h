class ProceduralRocksHelperFunctions
#include "CoreMinimal.h"
#include "Math/Vector.h"
#include "Engine/World.h"
#include "Kismet/BlueprintFunctionLibrary.h"

#include "ProceduralRocksHelperFunctions.generated.h"

UCLASS()
class  CIELIM_API UProceduralRocksHelperFunctions :
	public UBlueprintFunctionLibrary
{
public:
	GENERATED_BODY()
	
	UProceduralRocksHelperFunctions(const FObjectInitializer& ObjectInitializer);
	
	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static UStaticMesh GetStaticMeshCopy(UStaticMesh Mesh);

	UFUNCTION(BlueprintCallable, Category="Procedural Rocks Helper Functions")
	static UStaticMesh* GetStaticMeshCopy(UStaticMesh* DesiredMesh);
};

