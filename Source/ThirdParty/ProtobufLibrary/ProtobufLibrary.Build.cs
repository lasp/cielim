using UnrealBuildTool;
using System.IO;

public class ProtobufLibrary : ModuleRules
{
	public ProtobufLibrary(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	    bAddDefaultIncludePaths = false;

        PublicDefinitions.Add("_ALLOW_MSC_VER_MISMATCH");

        if (Target.Platform != UnrealTargetPlatform.Mac)
        { 
            string Err = string.Format("Protobuf runtime not available for platform {0}", Target.Platform.ToString());
            throw new BuildException(Err);
        }

        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;

        // PublicDefinitions.Add("CXXFLAGS=-Wno-undef-prefix");
        PublicAdditionalLibraries.Add(Path.Combine(ModuleDirectory, "lib/libprotobuf.a"));
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "include"));
	}
}
