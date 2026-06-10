using UnrealBuildTool;
using System;
using System.IO;

public class cielim : ModuleRules
{
	public cielim(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		bEnableExceptions = true;	// Allow c++ exception handling

		// Log platform and architecture in console output for debugging
		Console.WriteLine("Platform: " + Target.Platform);
		Console.WriteLine("Architecture: " + Target.Architecture);

		// Add engine module dependencies
		PrivateDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "ImageCore", "RenderCore", "Renderer", "RHI", "ProceduralMeshComponent" });
		PrivateIncludePaths.AddRange(new string[] {  Path.Combine(GetModuleDirectory("Renderer"), "Internal") });

		// Add third party module dependencies
		PrivateDependencyModuleNames.AddRange(new string[] { "Protobuf", "ZMQ" });

		// Add vcpkg includes

		string VcpkgDir = Path.Combine(Target.ProjectFile.Directory.FullName, "vcpkg_installed");

		string Architecture = Target.Architecture.ToString().Contains("arm64") ? "arm64" : "x64";

		if (Target.Platform == UnrealTargetPlatform.Mac)
		{
			PrivateIncludePaths.Add(Path.Combine(VcpkgDir, $"{Architecture}-osx", "include"));
		}
		else if (Target.Platform == UnrealTargetPlatform.Linux)
        {
			PrivateIncludePaths.Add(Path.Combine(VcpkgDir, $"{Architecture}-linux", "include"));
        }
        else if (Target.Platform == UnrealTargetPlatform.Win64)
        {
			PrivateIncludePaths.Add(Path.Combine(VcpkgDir, $"{Architecture}-windows-static-md", "include"));
        }
        else
        { 
            throw new BuildException($"Unsupported platform: {Target.Platform}");
        }
	}
}
