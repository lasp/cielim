import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

base_path = os.path.dirname(os.path.abspath(__file__))


def clean():
    print("Cleaning build files...")

    folders_to_clean = ["build", "content"]

    for folder in folders_to_clean:
        dir = os.path.join(base_path, folder)

        if os.path.isdir(dir):
            shutil.rmtree(dir)
            print(f"Removed {folder}/")
        else:
            print(f"{folder}/ already cleaned")


def compile_shaders():
    print("Compiling shaders...")

    if shutil.which("slangc") is None:
        raise FileNotFoundError("Slang compiler (slangc) not detected")

    source_dir = Path(os.path.join(base_path, "assets", "shaders"))
    output_dir = Path(os.path.join(base_path, "content", "shaders"))

    for shader in source_dir.rglob("*.slang"):
        relative_path = shader.relative_to(source_dir).with_suffix(".spv")
        out_path = output_dir / relative_path

        out_path.parent.mkdir(parents=True, exist_ok=True)

        process = subprocess.Popen(
            [
                "slangc",
                str(shader),
                "-target",
                "spirv",
                "-fvk-use-entrypoint-name",
                "-entry",
                "VertMain",
                "-entry",
                "FragMain",
                "-o",
                str(out_path),
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        process.wait()

        print(f"Finished compiling {shader.name}")


def configure(platform_name: str, preset: str):
    print(f"Configuring build for {platform_name} as {preset}...")

    # Generate build files and install vcpkg dependencies with CMake
    process = subprocess.Popen(
        [
            "cmake",
            "--preset",
            f"{preset}",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    process.wait()

    # Copy compile_commands.json to base build directory for Clangd

    target_path = os.path.join(base_path, "build", preset, "compile_commands.json")
    link_path = os.path.join(base_path, "build", "compile_commands.json")

    if os.path.isfile(target_path):
        if os.path.exists(link_path):
            os.remove(link_path)
        try:
            os.symlink(target_path, link_path)
        except PermissionError as e:
            print(f"Skipped compile_commands.json symlink, permission denined: {e}")


def build(platform_name: str, preset: str):
    print(f"Building for {platform_name} as {preset}...")

    # Build binaries with CMake
    process = subprocess.Popen(
        [
            "cmake",
            "--build",
            f"{os.path.join(base_path, "build", preset)}",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    process.wait()


if __name__ == "__main__":
    if shutil.which("cmake") is None:
        raise FileNotFoundError("CMake installation not detected")

    system = platform.system().lower()  # Operating system name
    machine = platform.machine().lower()  # System architecture name

    if machine in ("x86_64", "amd64"):
        architecture = "x64"
    elif machine in ("arm64", "aarch64"):
        architecture = "arm64"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    if system == "windows":
        platform_name = f"{architecture} Windows"
    elif system == "darwin":
        platform_name = f"{architecture} Mac"
    elif system == "linux":
        platform_name = f"{architecture} Linux"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    # Check arguments

    parser = argparse.ArgumentParser(description="Add options for building Cielim")
    parser.add_argument("-x", "--clean", action="store_true", help="Clean Cielim build files")
    parser.add_argument("-s", "--shaders", action="store_true", help="Compile shaders into SPIR-V")
    parser.add_argument("-c", "--config", action="store_true", help="Configure Cielim build files")
    parser.add_argument("-b", "--build", action="store_true", help="Build Cielim")
    parser.add_argument("-p", "--preset", type=str, default="", help="CMake preset to use for building")

    args, remaining_args = parser.parse_known_args()

    preset: str = args.preset

    # Create build config if it doesn't exist
    if os.path.exists("build_config.json"):
        with open("build_config.json", "r") as config_file:
            config = json.load(config_file)
    else:
        config = {}

    # If string is empty, check for build config, otherwise use defaults
    if not preset:
        if "preset" in config:
            preset = config["preset"]
        elif system == "windows":
            preset = "develop-windows"
        else:
            preset = "develop"

    # Save preset to build_config.json
    if "preset" not in config or config["preset"] is not preset:
        print(f"Saving preset {preset} to build_config.json...")
        config["preset"] = preset
        with open("build_config.json", "w") as config_file:
            json.dump(config, config_file)

    ranAtLeastOnce = False

    if args.clean:
        clean()
        ranAtLeastOnce = True
    if args.shaders:
        compile_shaders()
        ranAtLeastOnce = True
    if args.config:
        configure(platform_name, preset)
        ranAtLeastOnce = True
    if args.build:
        build(platform_name, preset)
        ranAtLeastOnce = True

    # If no command has been run, default to full clean run
    if not ranAtLeastOnce:
        clean()
        compile_shaders()
        configure(platform_name, preset)
        build(platform_name, preset)
