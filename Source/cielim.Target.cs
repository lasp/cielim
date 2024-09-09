using UnrealBuildTool;
using System;

// This is used for logging
using EpicGames.Core;

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
		
        ExtraModuleNames.AddRange(new string[] {"cielim", "OpenCV", "ProtobufLibrary", "ZMQ"});

        PreBuildThirdParty(this);
	}

    static public void PreBuildThirdParty(TargetRules targetRules)
    {
        Log.TraceInformation("Building pre-compile steps");

        // Tell the compiler to execute these commands before compiling the rest of the project

		if (targetRules.Platform == UnrealTargetPlatform.Linux || targetRules.Platform == UnrealTargetPlatform.Mac)
		{
			string command = "tcsh";
			string relativePath = "$(ProjectDir)/Source/ThirdParty/";

			// These are the literal commands to be executed
			string OpenCV_step = String.Format("{0} {1}OpenCV/OpenCV_build.sh \"{2}OpenCV/\"", command, relativePath, relativePath);
			string PB_step = String.Format("{0} {1}ProtobufLibrary/ProtobufLibrary_build.sh \"{2}ProtobufLibrary/\"", command, relativePath, relativePath);
			string ZMQ_step = String.Format("{0} {1}ZMQ/ZMQ_build.sh \"{2}ZMQ/\"", command, relativePath, relativePath);

			targetRules.PreBuildSteps.AddRange(new string[] {OpenCV_step, PB_step, ZMQ_step});
		}
		else
		{
            throw new BuildException("Build failed; your platform must be Mac.");
		}
    }
}
