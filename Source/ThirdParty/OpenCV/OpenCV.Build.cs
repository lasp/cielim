using UnrealBuildTool;
using System.IO;

public class OpenCV : ModuleRules
{
	public OpenCV(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	    bAddDefaultIncludePaths = false;
        
        if (Target.Platform == UnrealTargetPlatform.Win64)
        { 
            string Err = string.Format("OpenCV library not available for platform {0}", Target.Platform.ToString());
            throw new BuildException(Err);
        }
        
        PublicDefinitions.Add("_ALLOW_MSC_VER_MISMATCH");
        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;
        PublicPreBuildLibraries.Add(Path.Combine(ModuleDirectory, "lib/libopencv_core.dylib"));
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "include/opencv4"));
	}
}
