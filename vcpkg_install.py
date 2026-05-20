import os
import platform
import shutil
import subprocess
from pathlib import Path


def get_triplet():
    system = platform.system().lower()  # Operating system name
    machine = platform.machine().lower()  # System architecture name

    if machine in ("x86_64", "amd64"):
        architecture = "x64"
    elif machine in ("arm64", "aarch64"):
        architecture = "arm64"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    # All libraries are static and so only static triplets should be used
    if system == "windows":
        return f"{architecture}-windows-static-md"
    elif system == "darwin":
        return f"{architecture}-osx"
    elif system == "linux":
        return f"{architecture}-linux"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


# Installs dependencies using vcpkg. Returns -1 on failure and 1 when packages are already installed, else 0.
def install_vcpkg_packages():
    if shutil.which("vcpkg") is None:
        print("Vcpkg installation not detected")
        return -1

    project_root = str(Path(__file__).resolve().parent)

    triplet = None

    try:
        triplet = get_triplet()
    except RuntimeError as e:
        print(f"Error getting vcpkg triplet: {e}")
        return -1

    vcpkg_installed = os.path.join(project_root, "vcpkg_installed")

    # Check if dependencies have already been installed by using libprotobuf as heuristic

    if platform.system().lower() == "windows":
        heuristic = "libprotobuf.lib"
    else:
        heuristic = "libprotobuf.a"

    if os.path.isfile(os.path.join(vcpkg_installed, triplet, "lib", heuristic)):
        print(f"Vcpkg dependencies already installed for {triplet}")
        return 1

    print(f"Installing vcpkg dependencies for {triplet}...")

    try:
        subprocess.run(
            [
                "vcpkg",
                "install",
                f"--triplet={triplet}",
                f"--x-manifest-root={project_root}",
                f"--x-install-root={vcpkg_installed}",
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Vcpkg install failed with exit code {e.returncode}")
        return -1

    return 0


if __name__ == "__main__":
    install_vcpkg_packages()
