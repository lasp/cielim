# cielim
A photorealistic image generation tool for the space environment.

## Building the Project

### Cloning

The repository uses git submodules to manage dependencies. To ensure all submodules are cloned
properly, add the `--recurse-submodules` argument when doing git clone. For example:

`git clone https://github.com/lasp/cielim.git --recurse-submodules`

### Dependencies

To build this project install Unreal Engine (Currently version 5.4). Additionally, the following tools need to be installed and added to your PATH environment variable:

#### Linux
  - Automake
  - Autoconf
  - Libtool
  - Make
  - CMake (3.0 or higher)
  - Python (3.0 or higher)
#### Mac
  - Automake `brew install automake`
  - Autoconf `brew install autoconf`
  - Libtool `brew install libtool`
  - Make `brew install make`
  - CMake (3.0 or higher) `brew install cmake`
  - python (3.0 or higher)
#### Windows
  - Visual Studio Community 2022 and MSVC Build Tools
  - CMake (3.0 or higher)
  - Python (3.0 or higher)

**Note:** If you have both Visual Studio and Msys2/MinGW on your Windows machine, you may have issues building OpenCV as it may try to use MinGW to build files generated for Visual Studio. In this case, rename or delete your Msys64 folder while building and then restore it when it's finished.

**Additionally:** If you're working on Windows, you will need to copy and paste the .dll files corresponding to the linked .lib files in your `cielim\Binaries\Win64` directory. These include:
- libprotobuf.dll
- libzmq-(version).dll
- opencv_world(version).dll
- opencv_videoio_ffmpeg(version).dll

### Build Process

Building, cooking, and packaging Cielim can all be done using the `build.py` script. It can take the following command line arguments:
- `-b or --build` This argument tells it to build Cielim.
- `-c or --cook` This argument tells it to cook the content for Cielim.
- `-p or --package` This argument tells it to package the Cielim executable.
- `-r or --run` This argument tells it to run Cielim in the editor when the other tasks have finished.
- `-d or --debug` This argument can take one of three values: `DebugGame`, `Development`, or `Shipping` which specify the debug mode that Cielim should be built/packaged in. It is recommended to stay on `Development` which is the default debug value.

Alternatively, you can just run `build.py` with no arguments and this will build, cook, and package Cielim sequentially.
You can also choose to cook and package Cielim from the Unreal Editor for more control over the process which is explained
in a later section of this document.

In order to run Cielim in the Unreal Editor, you can double click on the `cielim.uproject` file which will open the editor. Additionally, you can run Cielim from `build.py` and feed it arguments or launch the Unreal Editor from your IDE directly.

To generate project files for your IDE of choice, either double click on the .uproject file and click "Generate ... project files" or open the .uproject with your IDE, or both.

### Common Errors When Working

There are several common errors that you may encounter when working with the source code:
- `Expecting to find a type to be declared in a module rules named 'cielim' in 'Unknown Assembly'. This type must derive from the 'ModuleRules' type defined by UnrealBuildTool`.
If you encounter this error, it means that you have modified one of the Target.cs or Build.cs files and they now contain an error. Resolve the issues in these files and this error will go away.
- `Missing third party include files`.
If you get a compilation error saying one or many third party includes are missing, this is most likely due to one or multiple of the third party libraries not being built. Make sure you have all of the dependencies installed. Alternatively, try deleting the Intermediate folder in /cielim and opening theBuild.cs files.
- `Third party library directories could not be found`.
If this happens, it means you didn't pull the git submodules when cloning the cielim repository. Try pulling the git submodules or cloning their repositories into their respectives folders under the ThirdParty folder directly.
- Errors linking to `UnrealEditor-DetailCustomizations.dylib` or `UnrealEditor-UMGEditor.dylib` during cooking or packaging can occur when your UE5 was recently updated. Go to your Epic Games and "Verify" your current engine version. Launch the editor from Epic Games (by hitting the launch on the engine version) to ensure it links all libraries properly on your machine.

### Packaging Game as Standalone Build
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
