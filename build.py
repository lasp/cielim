import os
import sys
import glob
import platform
import subprocess
import argparse
import json


def build(platform_name, executable_path, debug_mode):
    print(f"Building for {platform_name} {platform.machine()} as {debug_mode}...")

    cielim_path = os.path.dirname(os.path.abspath(__file__))

    process = subprocess.Popen(
        [
            f"{executable_path}",
            "BuildCookRun",
            f"-project={cielim_path}/cielim.uproject",
            f"-platform={platform_name}",
            f"-clientconfig={debug_mode}",
            "-build",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    process.wait()


def cook(platform_name, executable_path):
    print("Cooking content...")

    cielim_path = os.path.dirname(os.path.abspath(__file__))

    process = subprocess.Popen(
        [
            f"{executable_path}",
            "BuildCookRun",
            f"-project={cielim_path}/cielim.uproject",
            f"-platform={platform_name}",
            "-cook",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    process.wait()


def package(platform_name, executable_path, debug_mode):
    print("Packaging...")

    cielim_path = os.path.dirname(os.path.abspath(__file__))

    process = subprocess.Popen(
        [
            f"{executable_path}",
            "BuildCookRun",
            f"-project={cielim_path}/cielim.uproject",
            f"-platform={platform_name}",
            f"-clientconfig={debug_mode}",
            "-skipbuild",
            "-skipcook",
            "-stage",
            "-pak",
            "-archive",
            f"-archivedirectory={cielim_path}/Binaries/packageBuild/Mac",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    process.wait()


def fullBuildCookRun(platform_name, executable_path, debug_mode):
    print("Doing full run...")

    cielim_path = os.path.dirname(os.path.abspath(__file__))

    process = subprocess.Popen(
        [
            f"{executable_path}",
            "BuildCookRun",
            f"-project={cielim_path}/cielim.uproject",
            f"-platform={platform_name}",
            f"-clientconfig={debug_mode}",
            "-build",
            "-cook",
            "-stage",
            "-pak",
            "-archive",
            f"-archivedirectory={cielim_path}/Binaries/packageBuild/Mac",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    process.wait()


def run_editor(editor_path, args):
    print("Running Cielim in Unreal Editor...")

    cielim_path = os.path.dirname(os.path.abspath(__file__))

    process = subprocess.Popen(
        [f"{editor_path}", f"{cielim_path}"] + args, stdout=sys.stdout, stderr=sys.stderr
    )

    process.wait()


def retrieve_default_unreal_path():
    os_name = platform.system()
    unreal_path = None

    print(f"Build platform: {os_name} {platform.machine()}")
    
    if os_name == "Darwin":
        default_location = "/Users/Shared/Epic Games/UE_5*"
    elif os_name == "Windows":
        default_location = "C:/Program Files/Epic Games/UE_5*"
    else:
        default_location = "~/UnrealEngine/UE_5*"

    for dir in glob.glob(default_location):
        if os.path.exists(os.path.join(dir, "Engine/Build/BatchFiles")):
            unreal_path = dir
            break

    if unreal_path is None:
        print("Unreal path not found, provide path in the file build_config.json as "
              "{\"unreal_path\" : \"your_path_to_unreal\"}")

    return unreal_path


if __name__ == "__main__":
    # Check arguments for build, cook, package, and debug mode

    parser = argparse.ArgumentParser(description="Build, cook, and/or package Cielim")
    parser.add_argument("-b", "--build", action="store_true", help="Build Cielim source code")
    parser.add_argument("-c", "--cook", action="store_true", help="Cook content files for Cielim")
    parser.add_argument("-p", "--package", action="store_true", help="Package Cielim as standalone executable")
    parser.add_argument("-r", "--run", action="store_true", help="Run Cielim in Unreal Editor")
    parser.add_argument("-f", "--configfile", type =str, help="Provide a configuration file "
                                                                        "path to build_config.json")
    parser.add_argument("-d", "--debug", choices={"Development", "DebugGame", "Shipping"}, default="Development")

    args, remaining_args = parser.parse_known_args()

    unreal_path = None
    if args.configfile:
        print(f"Config file found at {args.configfile}")
        config = json.load(open(args.configfile, "r"))
        if "unreal_path" in config:
            unreal_path = config["unreal_path"]
    else:
        print(f"No config file found, retrieving default unreal path")
        unreal_path = retrieve_default_unreal_path()

    os_name = platform.system()
    if os_name == "Darwin":
        editor = "Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
        executable = "Engine/Build/BatchFiles/RunUAT.sh"
        platform_name = "Mac"
    elif os_name == "Windows":
        editor = "Engine/Binaries/Win64/UnrealEditor.exe"
        executable = "Engine/Build/BatchFiles/RunUAT.bat"
        platform_name = "Win64"
    elif os_name == "Linux":
        editor = "Engine/Binaries/Linux/UnrealEditor"
        executable = "Engine/Build/BatchFiles/RunUAT.sh"
        platform_name = "Linux"
    else:
        editor = "NA"
        executable = "NA"
        platform_name = "NA"


    debug_mode = args.debug

    ranAtLeastOnce = False

    if args.build:
        build(platform_name, os.path.join(unreal_path, executable), debug_mode)
        ranAtLeastOnce = True
    if args.cook:
        cook(platform_name, os.path.join(unreal_path, executable))
        ranAtLeastOnce = True
    if args.package:
        package(platform_name, os.path.join(unreal_path, executable), debug_mode)
        ranAtLeastOnce = True
    if args.run:
        run_editor(os.path.join(unreal_path, editor), remaining_args)
        ranAtLeastOnce = True

    # If no command has been run, default to full run
    if ranAtLeastOnce == False:
        fullBuildCookRun(platform_name, os.path.join(unreal_path, executable), debug_mode)
