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
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
        WindowsPlatform.bStripUnreferencedSymbols = false;
        CppStandard = CppStandardVersion.Cpp17;
        
        bUseFastPDBLinking = false;
        bPublicSymbolsByDefault = true;  // Forced to true on Windows anyways
		
        ExtraModuleNames.AddRange(new string[] {"cielim", "OpenCV", "ProtobufLibrary", "ZMQ"});
	}
}
