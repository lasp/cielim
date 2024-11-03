using UnrealBuildTool;
using System.IO;

public class cielim : ModuleRules
{
	public cielim(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

                bEnableExceptions = true;

		// Add module dependencies

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore"});

		PrivateDependencyModuleNames.AddRange(new string[] { "OpenCV", "ProtobufLibrary", "ZMQ"});

		// This is necessary for Pre/PostOpenCVHeaders
		PublicIncludePaths.Add("$(ProjectDir)/Source/ThirdParty");
	}
}
