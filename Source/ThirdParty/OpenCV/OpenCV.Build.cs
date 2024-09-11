using UnrealBuildTool;
using System.IO;

public class OpenCV : ModuleRules
{
	public OpenCV(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	    bAddDefaultIncludePaths = false;
        
        if (Target.Platform != UnrealTargetPlatform.Mac)
        { 
            string Err = string.Format("OpenCV library not available for platform {0}", Target.Platform.ToString());
            throw new BuildException(Err);
        }
        
        PublicDefinitions.Add("_ALLOW_MSC_VER_MISMATCH");

        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;

        // Link program to OpenCV Library files (these should all be included in libopencv_world)
        PublicAdditionalLibraries.Add(Path.Combine(ModuleDirectory, "build/lib/libopencv_world.dylib"));

        // Add include path for OpenCV headers
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "opencv/include/opencv4/opencv2"));
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "opencv/modules/core/include"));
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "opencv/modules/imgproc/include"));
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "build"));
	}
}
