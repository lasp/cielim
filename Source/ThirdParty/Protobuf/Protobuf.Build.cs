using UnrealBuildTool;
using System.IO;

public class Protobuf : ModuleRules
{
	public Protobuf(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	    bAddDefaultIncludePaths = false;

        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;

        // Link protobuf library

        string VcpkgDir = Path.Combine(Target.ProjectFile.Directory.FullName, "vcpkg_installed");

		string Architecture = Target.Architecture.ToString().Contains("arm64") ? "arm64" : "x64";

        string LibDirectory;

		if (Target.Platform == UnrealTargetPlatform.Mac)
		{
            LibDirectory = Path.Combine(VcpkgDir, $"{Architecture}-osx", "lib");
			PublicAdditionalLibraries.Add(Path.Combine(LibDirectory, "libprotobuf.a"));
		}
		else if (Target.Platform == UnrealTargetPlatform.Linux)
        {
            LibDirectory = Path.Combine(VcpkgDir, $"{Architecture}-linux", "lib");
			PublicAdditionalLibraries.Add(Path.Combine(LibDirectory, "libprotobuf.a"));
        }
        else if (Target.Platform == UnrealTargetPlatform.Win64)
        {
            LibDirectory = Path.Combine(VcpkgDir, $"{Architecture}-windows-static-md", "lib");
			PublicAdditionalLibraries.Add(Path.Combine(LibDirectory, "libprotobuf.lib"));
        }
        else
        { 
            throw new BuildException($"Unsupported platform: {Target.Platform}");
        }

        // Link all Abseil libraries

        foreach (string Lib in Directory.GetFiles(LibDirectory))
        {
            string FileName = Path.GetFileName(Lib);

            bool IsAbsl = FileName.StartsWith("absl_") || FileName.StartsWith("libabsl_");

            bool IsUtf8 = FileName.StartsWith("utf8_") || FileName.StartsWith("libutf8_");

            if (IsAbsl || IsUtf8)
            {
                PublicAdditionalLibraries.Add(Lib);
            }
        }
	}
}
