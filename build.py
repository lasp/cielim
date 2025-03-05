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


if __name__ == "__main__":
    os_name = platform.system()

    print(f"Build platform: {os_name} {platform.machine()}")

    unreal_path = None

    # Check if build_config.json already exists

    config = None

    if os.path.exists("build_config.json"):
        config = json.load(open("build_config.json", "r"))
    else:
        config = {}

    # Check if unreal_path field is set and valid

    if "unreal_path" in config and os.path.exists(config["unreal_path"] + "/Engine/Build/BatchFiles"):
        unreal_path = config["unreal_path"]
        print(f"Unreal path located from build config at {unreal_path}...")
    else:
        print("Build config not found or path invalid; checking default location")

        # Check default locations

        default_location = ""

        if os_name == "Darwin":
            default_location = "/Users/Shared/Unreal Engine/UE_5*"
        elif os_name == "Windows":
            default_location = "C:/Program Files/Epic Games/UE_5*"
        else:
            default_location = "~/UnrealEngine/UE_5*"

        for dir in glob.glob(default_location):
            if os.path.exists(os.path.join(dir, "/Engine/Build/BatchFiles")):
                unreal_path = dir
                break

        if unreal_path is None:
            unreal_path = input("Input the absolute path to your Unreal Engine installation: ").strip()

        # If the path is valid, save it to the config file

        if os.path.exists(f"{unreal_path}/Engine/Build/BatchFiles"):
            print("Saving path to build_config.json...")
            config["unreal_path"] = unreal_path
            json.dump(config, open("build_config.json", "w"))
        else:
            print('Path provided was incorrect; expected something like ".../UnrealEngine/UE_5.4"')
            exit()

    # Check arguments for build, cook, package, and debug mode

    parser = argparse.ArgumentParser(description="Build, cook, and/or package Cielim")
    parser.add_argument("-b", "--build", action="store_true", help="Build Cielim source code")
    parser.add_argument("-c", "--cook", action="store_true", help="Cook content files for Cielim")
    parser.add_argument("-p", "--package", action="store_true", help="Package Cielim as standalone executable")
    parser.add_argument("-r", "--run", action="store_true", help="Run Cielim in Unreal Editor")
    parser.add_argument("-d", "--debug", choices={"Development", "DebugGame", "Shipping"}, default="Development")

    args, remaining_args = parser.parse_known_args()


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
