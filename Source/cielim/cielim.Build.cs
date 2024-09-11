using UnrealBuildTool;
using System.IO;

public class cielim : ModuleRules
{
	public cielim(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		// Add module dependencies

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore"});

		PrivateDependencyModuleNames.AddRange(new string[] { "OpenCV", "ProtobufLibrary", "ZMQ"});

		PublicIncludePaths.Add("$(ProjectDir)/Source/ThirdParty");
	}
}
