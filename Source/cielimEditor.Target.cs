using UnrealBuildTool;
using System;

// This is used for logging
using EpicGames.Core;

public class cielimEditorTarget : TargetRules
{
	public cielimEditorTarget( TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		
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
