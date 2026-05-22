# Building Cielim

## Prerequisites

### Unreal Engine 5.6

Install Unreal Engine 5.6 via the Epic Games Launcher. The build script will check that the engine is installed in the default location ``/Users/Shared/Epic Games/UE_5.6`` (Mac) or ``C:/Program Files/Epic Games/UE_5.6`` (Windows). If the engine is not found in the default location, a location will need to be provided which is then recorded in ``build_config.json``.

### vcpkg

Cielim uses [vcpkg](https://vcpkg.io) in **manifest mode** to manage its C++ third-party dependencies (zeromq, cppzmq, protobuf). vcpkg must be installed separately and does **not** live inside this repository.

1. Clone and bootstrap vcpkg once.

      ```bash
      git clone https://github.com/microsoft/vcpkg
      cd vcpkg
      ./bootstrap-vcpkg.sh -disableMetrics   # Mac / Linux
      bootstrap-vcpkg.bat -disableMetrics    # Windows
      ```

2. Set the ``VCPKG_ROOT`` environment variable to the vcpkg installation directory and add it to PATH, and add to your shell profile so it persists across sessions.

      ```bash
      # ~/.zshrc or ~/.bash_profile (Mac/Linux)
      export VCPKG_ROOT="<vcpkg_install_directory>"
      export PATH="$VCPKG_ROOT:$PATH"
      ```

   For Windows, these must be added as system or user environment variables.

### Python

The build script ``build.py`` requires Python 3. No additional packages beyond the standard library are needed.

## Building

The project can be built from an IDE such as Rider or from the build script ``build.py``. When running the build script, options can be added to limit to just building, cooking assets / shaders, etc. These are elaborated in the Wiki pages for this repository.

   ```bash
   python3 build.py           # Build, cook, and package executable
   python3 build.py --build   # Only build files
   ```

The script will:

1. Locate the Unreal Engine installation.
2. Invoke ``RunUAT`` → ``BuildCookRun`` to build the editor target.

As part of the Unreal Build Tool (UBT) **PreBuildSteps**, the python script ``vcpkg_install.py`` is called before the project source files are compiled which installs dependencies using vcpkg. Alternatively, this script can be called manually. If the dependencies are already installed, the script will do nothing.

Vcpkg runs in **manifest mode**: dependencies and version overrides are declared in ``vcpkg.json``. If the packages are already up-to-date it exits in milliseconds. Libraries are installed to ``<ProjectDir>/vcpkg_installed/<triplet>/`` and are ignored by git.

It is important that the toolchain version that vcpkg uses to build the dependencies **is the exact same** as the toolchain version used when building the project source files, otherwise you will experience linking errors. For example, if on Windows, vcpkg will say something like ``Compiler found: <path_to_MSVC>/<MSVC_version>/bin/Hostx64/x64/cl.exe``, and the Unreal Build Tool (UBT) will output something like ``Using Visual Studio 2022 <MSVC_version> toolchain``. If those two versions do not match exactly, you will get linking errors.

## Supported Platforms

| Platform | vcpkg triplet | Linkage |
| -------- | ------------- | ------- |
| MacOS | ``arm64-osx`` | Static (.a) |
| Linux | ``x64-linux`` | Static (.a) |
| Windows | ``x64-windows-static-md`` | Static (.lib) |

**Note**: Both arm64 and x64 architectures are supported for all platforms and the correct one is selected automatically.

## Regenerating Protobuf Sources

The generated files ``Source/cielim/Protobuf/cielimMessage.pb.{h,cc}`` and ``Source/cielim/Protobuf/imageDiagnostics.pb.{h,cc}`` must be regenerated whenever the corresponding ``.proto`` files change. Use the **same protoc version** as the linked library to avoid header/binary mismatches.

After a successful vcpkg install, the matching protoc binary is available as a symlink in the installed tree. The generated files can then be rebuilt using the python script ``build_protobuf.py`` or manually.

   ```bash
   PROTOC="vcpkg_installed/<triplet>/tools/protobuf/protoc"
   PROTO_DIR="Source/cielim/Protobuf"
   PROTO_DIR_PY="Source/cielim-python/cielim"

   $PROTOC --proto_path=$PROTO_DIR --cpp_out=$PROTO_DIR --python_out=$PROTO_DIR_PY cielimMessage.proto imageDiagnostics.proto
   ```

## Troubleshooting

- ``VCPKG_ROOT is not set`` / linker errors for zmq or protobuf symbols:

   Ensure ``VCPKG_ROOT`` is exported in your shell environment **before** launching the build. Also verify toolchain version match as described in the *Building* section of this document. If on MacOS, linking errors may also arise if CMake cannot locate your MacOS SDK version. This can be fixed by updating XCode / XCode Command Line Tools, or by manually exporting the `SDKROOT` environment variable.

   ```bash
   export SDKROOT="$(xcrun --sdk macosx --show-sdk-path)"
   ```

- ``vcpkg: command not found``:

   Bootstrap vcpkg first (see *Prerequisites* above) and confirm ``$VCPKG_ROOT/vcpkg`` is executable. Then add to PATH environment variable.

- ``error: This file was generated by a newer version of protoc``:

   The generated ``*.pb.h`` files are out of sync with the installed protobuf version. Regenerate them using the *Regenerating Protobuf Sources* instructions above.
