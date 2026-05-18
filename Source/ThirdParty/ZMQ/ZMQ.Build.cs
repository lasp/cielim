using UnrealBuildTool;
using System.IO;

public class ZMQ : ModuleRules
{
	public ZMQ(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;	
	    bAddDefaultIncludePaths = false;

        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;

        // Link to libzmq library

        string VcpkgDir = Path.Combine(Target.ProjectFile.Directory.FullName, "vcpkg_installed");

		string Architecture = Target.Architecture.ToString().Contains("arm64") ? "arm64" : "x64";

		if (Target.Platform == UnrealTargetPlatform.Mac)
		{
			PublicAdditionalLibraries.Add(Path.Combine(VcpkgDir, $"{Architecture}-osx", "lib", "libzmq.a"));
		}
		else if (Target.Platform == UnrealTargetPlatform.Linux)
        {
			PublicAdditionalLibraries.Add(Path.Combine(VcpkgDir, $"{Architecture}-linux", "lib", "libzmq.a"));
        }
        else if (Target.Platform == UnrealTargetPlatform.Win64)
        {
            PublicDefinitions.Add("ZMQ_STATIC");
			PublicAdditionalLibraries.Add(Path.Combine(VcpkgDir, $"{Architecture}-windows-static-md", "lib", "libzmq-mt-s-4_3_5.lib"));
        }
        else
        { 
            throw new BuildException($"Unsupported platform: {Target.Platform}");
        }
	}
}
