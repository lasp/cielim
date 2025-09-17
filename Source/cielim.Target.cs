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
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_6;

        WindowsPlatform.bStripUnreferencedSymbols = false;
        CppStandard = CppStandardVersion.Cpp20;
        
        bUseFastPDBLinking = false;
        bPublicSymbolsByDefault = true;  // Forced to true on Windows anyways
		
        ExtraModuleNames.Add("cielim");
	}
}
