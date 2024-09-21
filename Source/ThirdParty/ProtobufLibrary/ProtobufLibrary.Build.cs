using UnrealBuildTool;
using System.IO;

public class ProtobufLibrary : ModuleRules
{
	public ProtobufLibrary(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	    bAddDefaultIncludePaths = false;

        PublicDefinitions.Add("_ALLOW_MSC_VER_MISMATCH");

        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;

        // PublicDefinitions.Add("CXXFLAGS=-Wno-undef-prefix"); // This should get rid of unnecessary warnings

        // Link to protobuf libraries
        if (Target.Platform == UnrealTargetPlatform.Mac || Target.Platform == UnrealTargetPlatform.Linux)
        {
            PublicAdditionalLibraries.Add(Path.Combine(ModuleDirectory, "lib/libprotobuf.a"));
        }
        else if (Target.Platform == UnrealTargetPlatform.Win64)
        {
            PublicDefinitions.Add("PROTOBUF_USE_DLLS"); // This is needed for protobuf to compile to dlls
            
            PublicAdditionalLibraries.Add(Path.Combine(ModuleDirectory, "lib/libprotobuf.lib"));
        }
        else
        { 
            string Err = string.Format("Protobuf runtime not available for platform {0}", Target.Platform.ToString());
            throw new BuildException(Err);
        }

        // Add google headers to include path
        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "include"));
	}
}
