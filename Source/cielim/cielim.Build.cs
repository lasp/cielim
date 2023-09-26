using UnrealBuildTool;

public class cielim : ModuleRules
{
	public cielim(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "ZeroMQ"});

		PrivateDependencyModuleNames.AddRange(new string[] { "ProtobufLibrary" });
	}
}
