#include "CoreMinimal.h"
#include "Math/Vector.h"
#include "Engine/World.h"
#include "Kismet/BlueprintFunctionLibrary.h"

#include "ProceduralRocksHelperFunctions.generated.h"

UCLASS()
class  CIELIM_API UProceduralRocksHelperFunctions :
	public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
public:
	
	UProceduralRocksHelperFunctions(const FObjectInitializer& ObjectInitializer);
	
	UFUNCTION(BlueprintCallable, Category="Rendering Functions")
	static UStaticMesh* GetStaticMeshCopy(UStaticMesh* const Mesh);
};

