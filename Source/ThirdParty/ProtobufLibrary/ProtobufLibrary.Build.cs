using UnrealBuildTool;
using System.IO;

public class ProtobufLibrary : ModuleRules
{
    public const string RelativePathToProtobufModule = "Source/ThirdParty/ProtobufLibrary/";
    public const string RelativePathToProtobufIncludes = RelativePathToProtobufModule + "include/";
    public const string RelativePathToProtobufLibraries = RelativePathToProtobufModule + "lib/";

	public ProtobufLibrary(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	    bAddDefaultIncludePaths = false;

        string protobufLibraryLibDir = Path.Combine(ModuleDirectory, "lib/");
        string protobufLibraryIncludeDir = Path.Combine(ModuleDirectory, "include/");
        string libraryFile = ProtobufLibPath(Target);

        if (Target.Platform != UnrealTargetPlatform.Mac && Target.Platform != UnrealTargetPlatform.Linux)
        { 
            string Err = string.Format("Protobuf runtime not available for platform {0}", Target.Platform.ToString());
            throw new BuildException(Err);
        }
        // PublicDefinitions.Add("CXXFLAGS=-Wno-undef-prefix");
        PublicDefinitions.Add("_ALLOW_MSC_VER_MISMATCH");
        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;
        PublicPreBuildLibraries.Add(libraryFile);

        PublicIncludePaths.Add(protobufLibraryIncludeDir);
	}

    static public string ProtobufLibPath(ReadOnlyTargetRules targetRules)
    {
        string libraryName = "";
        
        if (targetRules.Platform == UnrealTargetPlatform.Mac || targetRules.Platform == UnrealTargetPlatform.Linux)
        {
            libraryName = "/libprotobuf.a";
        }
        else {
            string Err = string.Format("Protobuf library not found at {0}.", RelativePathToProtobufLibraries);
            throw new BuildException(Err);
        }

        // string relativePathToProtobufLib = RelativePathToProtobufLibraries + targetRules.Platform.ToString() + libraryName;
        string relativePathToProtobufLib = RelativePathToProtobufLibraries + libraryName;

        return Path.Combine(targetRules.ProjectFile.Directory.FullName, relativePathToProtobufLib);
    }
}
