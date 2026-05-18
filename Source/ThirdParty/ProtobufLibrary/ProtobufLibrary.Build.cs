using UnrealBuildTool;
using System.IO;

public class ProtobufLibrary : ModuleRules
{
	public ProtobufLibrary(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	    bAddDefaultIncludePaths = false;

        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;

        // Link protobuf library

        string VcpkgDir = Path.Combine(Target.ProjectFile.Directory.FullName, "vcpkg_installed");

		string Architecture = Target.Architecture.ToString().Contains("arm64") ? "arm64" : "x64";

		if (Target.Platform == UnrealTargetPlatform.Mac)
		{
			PublicAdditionalLibraries.Add(Path.Combine(VcpkgDir, $"{Architecture}-osx", "lib", "libprotobuf.a"));
		}
		else if (Target.Platform == UnrealTargetPlatform.Linux)
        {
			PublicAdditionalLibraries.Add(Path.Combine(VcpkgDir, $"{Architecture}-linux", "lib", "libprotobuf.a"));
        }
        else if (Target.Platform == UnrealTargetPlatform.Win64)
        {
			PublicAdditionalLibraries.Add(Path.Combine(VcpkgDir, $"{Architecture}-windows-static-md", "lib", "libprotobuf.lib"));
        }
        else
        { 
            throw new BuildException($"Unsupported platform: {Target.Platform}");
        }
	}
}
