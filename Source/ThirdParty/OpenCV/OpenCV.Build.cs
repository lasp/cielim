using UnrealBuildTool;
using System.IO;

public class OpenCV : ModuleRules
{
	public OpenCV(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	    bAddDefaultIncludePaths = false;
        
        
        PublicDefinitions.Add("_ALLOW_MSC_VER_MISMATCH");

        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;

        // Link program to OpenCV Library files (these should all be included in libopencv_world)
        if (Target.Platform == UnrealTargetPlatform.Mac || Target.Platform == UnrealTargetPlatform.Linux)
        {
            PublicAdditionalLibraries.Add(Path.Combine(ModuleDirectory, "opencv/build/lib/libopencv_world.dylib"));

            PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "opencv/include/opencv4/opencv2"));
        }
        else if (Target.Platform == UnrealTargetPlatform.Win64)
        {
            PublicAdditionalLibraries.Add(Path.Combine(ModuleDirectory, "opencv/build/lib/Release/opencv_world4100.lib"));

            PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "opencv/include/opencv2"));
        }
        else
        { 
            string Err = string.Format("OpenCV library not available for platform {0}", Target.Platform.ToString());
            throw new BuildException(Err);
        }

        // Add universal include path for OpenCV headers
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "opencv/modules/core/include"));
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "opencv/modules/imgproc/include"));
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "opencv/build"));
	}
}
