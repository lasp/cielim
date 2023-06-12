# cielim
A photorealistic image generation tool for the space environment 

## Building The Project
*Currently only Macos is supported.*

This project is in pretty early stages and the build system/process is probably flaky. If you find an issue please 
create an issue.

- [Install Unreal](https://www.unrealengine.com/en-US/download) (currently 5.2.0)
- Clone this repository
- `brew install automake`
- Open the cielim.uproject file
    - This will launch Unreal and if the project isn't built (which it won't be if you are starting fresh) it will 
	try to build the project.
	- If the build fails, one can get further debug informations about what might be failing by seeing the output 
	from a manual invocaiton of the build from the terminal (replacing any user specific paths) invoke the following
	- `/Users/Shared/Epic\ Games/UE_5.2/Engine/Binaries/ThirdParty/DotNet/6.0.302/mac-arm64/dotnet 
	"/Users/Shared/Epic\ Games/UE_5.2/Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.dll" 
	Development Mac -Project=/Users/pake0095/Documents/Repositories/cielim/cielim.uproject -TargetType=Editor 
	-Progress -NoEngineChanges -NoHotReloadFromIDE`
- Generate project files
    - From the editor Tools > Refresh/Generate Visual Studio Code Project
	- A project can be generated for either XCode, CLion, or VSCode
- To open the project in VSCode, from a terminal window run the following (this ensures that the VSCode terminal 
picks up your default terminal environment variables)
		- `code cielim.code-workspace`

NB: if you recieve a compilation error where certain protobuf headers aren't found, try deleting the Intermediate 
directory and touching the `ProtobufLibrary.Build.cs` file.
