using UnrealBuildTool;
using System.IO;

public class ZMQ : ModuleRules
{
	public ZMQ(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;	
	    bAddDefaultIncludePaths = false;

        PublicDefinitions.Add("_ALLOW_MSC_VER_MISMATCH");
        PublicDefinitions.Add("ZMQ_BUILD_DRAFT_API=1");
        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;

        // Link to libzmq libraries

        if (Target.Platform == UnrealTargetPlatform.Mac || Target.Platform == UnrealTargetPlatform.Linux)
        {
            // .a is unix specific library file
            PublicAdditionalLibraries.Add(Path.Combine(ModuleDirectory, "libzmq/build/lib/libzmq.a"));
        }
        else if (Target.Platform == UnrealTargetPlatform.Win64)
        {
            RuntimeDependencies.Add(Path.Combine(ModuleDirectory, "libzmq/build/bin/Release/libzmq-v143-mt-4_3_6.dll"));
            
            // .lib is windows specific library file
            PublicAdditionalLibraries.Add(Path.Combine(ModuleDirectory, "libzmq/build/lib/Release/libzmq-v143-mt-4_3_6.lib"));
        }
        else
        { 
            string Err = string.Format("ZMQ library not available for platform {0}", Target.Platform.ToString());
            throw new BuildException(Err);
        }

        // Add ZMQ headers to include path
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "cppzmq"));
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "libzmq/include"));
	}
}
