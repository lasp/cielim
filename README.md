# cielim
A photorealistic image generation tool for the space environment 

## Building The Project

This project is in pretty early stages and the build system/process is probably flaky. If you find an issue please 
create an issue.

### Dependencies

Firstly, to build this project you will need to install Unreal Engine (Currently version 5.4). Additionally, you will need the following 
tools installed on your computer and added to your PATH environment variable:
- Automake (only for MacOS and Linux)
- Autoconf (only for MacOS and Linux)
- Libtool (only for MacOS and Linux)
- Make (only for MacOS and Linux)
- Visual Studio Community 2022 and MSVC Build Tools (Windows Only)
- CMake version 3.0 or higher

**Note:** If you have both Visual Studio and Msys2/MinGW on your Windows machine, you may have issues building OpenCV as it may try to use MinGW to build
files generated for Visual Studio. In this case, rename or delete your Msys64 folder while building and then restore when it's finished.

**Additionally:** If you're working on Windows, you will need to copy and paste the .dll files corresponding to the linked .lib files in your `cielim\Binaries\Win64` directory. These include:
  - libprotobuf.dll
  - libzmq-(version).dll
  - opencv_world(version).dll
  - opencv_videoio_ffmpeg(version).dll

### Build Process

Next, you will need to open (double click) the cielim.uproject file  
- This will launch Unreal and if the project isn't built (which it won't be if you are starting fresh) it will try to build the project.
- If the build fails or you would like more information, you can get further debug by manually invoking the build from the terminal 
  (replacing any user specific paths) using the following:
  - `<Path to your UE installation>/UE_5.4/Engine/Binaries/ThirdParty/DotNet/6.0.302/mac-arm64/dotnet 
  "<Path to your UE installation>/UE_5.4/Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.dll" Development <Mac or Linux or Win64> 
  -Project=<Path to cielim folder>/cielim/cielim.uproject -TargetType=Editor -Progress -NoEngineChanges -NoHotReloadFromIDE`
- Generate project files
	- From the editor Tools > Refresh/Generate Visual Studio Code Project
	- A project can be generated for either XCode, CLion, or VSCode

To open the project in VSCode, from a terminal window run the following (this ensures that the VSCode terminal 
picks up your default terminal environment variables)
	- `code cielim.code-workspace`

 ### Common Errors When Working

 There are several common errors that you may encounter when working with the source code:
 - `Expecting to find a type to be declared in a module rules named 'cielim' in 'Unknown Assembly'. This type must derive from the 'ModuleRules' type defined by UnrealBuildTool.`
   If you encounter this error, it means that you have modified one of the Target.cs or Build.cs files and they now contain an error. Resolve the issues in these files and this
   error will go away.
- `Missing third party include files`. If you get a compilation error saying one or many third party includes are missing, this is most likely due to one or multiple of the
  third party libraries not being built. Make sure you have all of the dependencies installed. Alternatively, try deleting the Intermediate folder in /cielim and opening the
  Build.cs files.
- `Third party library directories could not be found`. If this happens, it means you didn't pull the git submodules when cloning the cielim repository. Try pulling the git submodules
  or cloning their repositories into their respectives folders under the ThirdParty folder directly.

## Packaging Game as Standalone Build
- Follow Guide in Unreal Documentation for [Releasing Your Project](https://docs.unrealengine.com/5.2/en-US/preparing-unreal-engine-projects-for-release/)
  - **Note:** Set build configuration to `Developement` instead of `Shipping`
  - In **Build** -> **Advanced Settings** make sure `Build UAT` is unchecked
  - Under **Cooked Platforms** check `Mac`
  - Under **Cooked Cultures** check `En`
  - Under **Cooked Maps** check only `Lvl_Visualization`
    - **Optional:** If you would like to build with the Main Menu UI check `Lvl_MainMenu` as well
- Once Project Launcher has completed locate the application in `/Binaries` and launch from there
- To use command line arguments locate application in `/Binaries` in a terminal and run:
  - **For Mac**: 
    - `open cielim.app --args -myflag`	
