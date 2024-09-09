using UnrealBuildTool;
using System;

// This is used for logging
using EpicGames.Core;
using System.IO;

public class cielimTarget : TargetRules
{
	public cielimTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;

        // Project settings
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;

        WindowsPlatform.bStripUnreferencedSymbols = false;
        CppStandard = CppStandardVersion.Cpp17;
        
        bUseFastPDBLinking = false;
        bPublicSymbolsByDefault = true;  // Forced to true on Windows anyways
		
        ExtraModuleNames.Add("cielim");

        PreBuildThirdParty(this);
	}

    static public void PreBuildThirdParty(TargetRules targetRules)
    {
        // Tell the compiler to execute these commands before compiling the rest of the project

		if (targetRules.Platform == UnrealTargetPlatform.Linux || targetRules.Platform == UnrealTargetPlatform.Mac)
		{
            Log.TraceInformation("Building pre-compile steps...");

            string projectDir = targetRules.ProjectFile.Directory.FullName;     // Get absolute project directory
            string relativePath = Path.Combine(projectDir, "Source", "ThirdParty");

			// These are the literal commands to be executed
			string OpenCV_step = String.Format("tcsh {0}/OpenCV/OpenCV_build.sh \"{1}/OpenCV/\"", relativePath, relativePath);
			string ProtoB_step = String.Format("tcsh {0}/ProtobufLibrary/ProtobufLibrary_build.sh \"{1}/ProtobufLibrary/\"", relativePath, relativePath);
			string ZMQ_step = String.Format("tcsh {0}/ZMQ/ZMQ_build.sh \"{1}/ZMQ/\"", relativePath, relativePath);

            Log.TraceInformation(OpenCV_step);
            Log.TraceInformation(ProtoB_step);
            Log.TraceInformation(ZMQ_step);

			targetRules.PreBuildSteps.AddRange(new string[] {OpenCV_step, ProtoB_step, ZMQ_step});
		}
		else
		{
            throw new BuildException("Build failed; your platform must be Mac.");
		}
    }
}
