using UnrealBuildTool;
using System.IO;

public class cielim : ModuleRules
{
	public cielim(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		bEnableExceptions = true;	// Allow c++ exception handling

		// Add module dependencies

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "RenderCore", "Renderer", "RHI", "ProceduralMeshComponent" });

		PrivateDependencyModuleNames.AddRange(new string[] { "ProtobufLibrary", "ZMQ" });
	}
}
