using UnrealBuildTool;
using System.IO;

public class ZMQ : ModuleRules
{
	public ZMQ(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;	
	    bAddDefaultIncludePaths = false;
	    
        string CppZmqIncludeDir = Path.Combine(ModuleDirectory, "cppzmq");
        string ZmqIncludeDir = Path.Combine(ModuleDirectory, "libzmq/include");
        string ZmqLibrary = Path.Combine(ModuleDirectory, "libzmq/build/lib/libzmq.a");
        
        if (Target.Platform == UnrealTargetPlatform.Win64)
        { 
            string Err = string.Format("ZMQ library not available for platform {0}", Target.Platform.ToString());
            throw new BuildException(Err);
        }
        
        PublicDefinitions.Add("_ALLOW_MSC_VER_MISMATCH");
        Type = ModuleRules.ModuleType.External;
        PrecompileForTargets = PrecompileTargetsType.Any;
        PublicPreBuildLibraries.Add(ZmqLibrary);
        PublicIncludePaths.Add(CppZmqIncludeDir);
        PublicIncludePaths.Add(ZmqIncludeDir);
	}
}
