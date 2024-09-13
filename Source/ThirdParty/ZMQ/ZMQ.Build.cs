using UnrealBuildTool;
using System.IO;

public class ZMQ : ModuleRules
{
	public ZMQ(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;	
	    bAddDefaultIncludePaths = false;
        
        if (Target.Platform == UnrealTargetPlatform.Win64)
        { 
            string Err = string.Format("ZMQ library not available for platform {0}", Target.Platform.ToString());
            throw new BuildException(Err);
        }

        PublicDefinitions.Add("_ALLOW_MSC_VER_MISMATCH");
        
        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;

        // Link to libzmq libraries
        PublicAdditionalLibraries.Add(Path.Combine(ModuleDirectory, "libzmq/build/lib/libzmq.a"));

        // Add ZMQ headers to include path
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "cppzmq"));
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "libzmq/include"));
	}
}
