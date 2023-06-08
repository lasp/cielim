using UnrealBuildTool;
using System.Collections.Generic;
using EpicGames.Core;
using System.IO;

public class cielimTarget : TargetRules
{
	public cielimTarget( TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V2;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_2;
		ExtraModuleNames.Add("cielim");

	
        Log.TraceInformation("Cielim Target Instantiating Protobuf_Library");
        bUseFastPDBLinking = false;
        bPublicSymbolsByDefault = true;  // Forced to true on Windows anyways
        WindowsPlatform.bStripUnreferencedSymbols = false;
        BuildProtobufLib(this);
        CppStandard = CppStandardVersion.Cpp17;
	}

	static public void BuildProtobufLib(TargetRules targetRules)
    {
        Log.TraceInformation("Protobuf_Library Setting PreBuildSteps");
        
        // string VersionPath = Path.Combine(ModuleDirectory, VersionNumber);
	    // string LibraryPath = Path.Combine(VersionPath, "lib");

        ReadOnlyTargetRules readOnlyTargetRules = new ReadOnlyTargetRules(targetRules);

        string BuildStep = ProtobufBuildStep(readOnlyTargetRules);
        string PreBuildStep = "";

        if (targetRules.Platform == UnrealTargetPlatform.Mac)
        {
            PreBuildStep += "tcsh ";
        }

        PreBuildStep += "$(ProjectDir)\\" + BuildStep + " \"$(ProjectDir)\\" + RelativePathToProtobufModule + "\"";

        // Alternative to Path.Combine, but ensures the path inside $(ProjectDir) is corrected
        PreBuildStep = PreBuildStep.Replace('/', Path.DirectorySeparatorChar).Replace('\\', Path.DirectorySeparatorChar);
        Log.TraceInformation(PreBuildStep);
        targetRules.PreBuildSteps.Add(PreBuildStep);
    }

	public const string RelativePathToProtobufModule = "Source/ThirdParty/ProtobufLibrary/";
    public const string RelativePathToProtobufIncludes = RelativePathToProtobufModule + "include";
    public const string RelativePathToProtobufLibraries = RelativePathToProtobufModule + "lib";

    static public string ProtobufBuildStep(ReadOnlyTargetRules targetRules)
    {
        if (targetRules.Platform == UnrealTargetPlatform.Mac)
        {
            return RelativePathToProtobufModule + "build-protobuf-library.sh";
        }
        else
        {
            string Err = string.Format("Protobuf not found for platform {0}", targetRules.Platform.ToString());

            // UE 5.0 did not invoke this for linux (which is not whitelisted as a project platform
            // UE 5.1 does, and the tooling fails here if an error is thrown.
            // TODO:  Find a graceful way of declining linux while not failing build tools on supported playforms.
            //        Or, (preferably), just add linux support.

            /*  
            throw new BuildException(Err);
            */

            return Err;
        }
    }
}
