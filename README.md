# cielim
A photorealistic image generation tool for the space environment

## Building The Project

This project is in pretty early stages and the build system/process is probably flaky. If you find an issue please
create an issue.

### Cloning

The repository uses git submodules to manage dependencies. To ensure all submodules are cloned
pass `--recurse-submodules` e.g.

`git clone https://github.com/lasp/cielim.git --recurse-submodules`

### Dependencies

To build this project install Unreal Engine (Currently version 5.4). Additionally, the following
tools need to be installed and added to your PATH environment variable:
#### Linux
  - Automake
  - Autoconf
  - Libtool
  - Make
  - CMake (3.0 or higher)
#### Mac
  - Automake `brew install automake`
  - Autoconf `brew install autoconf`ter
  - Libtool `brew install libtool`
  - Make `brew install make`
  - CMake `brew install cmake` (3.0 or higher)
#### Windows
  - Visual Studio Community 2022 and MSVC Build Tools
  - CMake version (3.0 or higher)

**Note:** If you have both Visual Studio and Msys2/MinGW on your Windows machine, you may have issues building OpenCV as it may try to use MinGW to build files generated for Visual Studio. In this case, rename or delete your Msys64 folder while building and then restore when it's finished.

**Additionally:** If you're working on Windows, you will need to copy and paste the .dll files corresponding to the linked .lib files in your `cielim\Binaries\Win64` directory. These include:
  - libprotobuf.dll
  - libzmq-(version).dll
  - opencv_world(version).dll
  - opencv_videoio_ffmpeg(version).dll

### Build Process

Open (double click) the cielim.uproject file
- This launches Unreal and if the project isn't built (which it won't be if you are starting fresh) it will try to build the project.
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

### pre-commit
Pre-commit is a tool used to automate code formatting for easy reading.
This allows the reviewer to focus on the architecture of a change and not simple nitpicks.

##### Installing pre-commit

Verify pre-commit is installed with:
```
$ pre-commit --version
pre-commit 3.6.2
```

If you are using python virtual environments, you may need to activate your environment to use pre-commit.

Then run ```pre-commit install``` to set up the git hook scripts.
You must run this inside of the repo and will only be installed inside that repository.
```
$ pre-commit install
pre-commit installed at .git/hooks/pre-commit
```
Now ```pre-commit``` will run automatically whenever you run ```git commit```!

When ```pre-commit``` decides to edit some of your files,
you will need to add those changes to your commit and commit again.

##### Manually Running pre-commit
For cases where pre-commit does not automatically run (for example when first installing and using pre-commit), you
can manually run pre-commit on specific files you have edited. Use the command:
```
$ pre-commit run --files <file>
```
Note that you must run this command inside the directory containing the file you are running pre-commit on.

##### Formatting Exceptions
If there is a section of python code you want pre-commit to leave alone, wrap the section with ```# fmt: off``` and ```# fmt: on``` like this:

```
# fmt: off
custom_formatting = [
    0, 1, 2,
    3, 4, 5,
    6, 7, 8
]
# fmt: on
```

This tells pre-commit to turn formatting off until you tell it to turn back on again.
