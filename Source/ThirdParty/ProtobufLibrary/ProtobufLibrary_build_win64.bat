@echo off
echo Current working directory: %CD%
echo Relative path: %~1

:: Path from build directory to libprotobuf library file
set "protobuf_lib_path=lib\libprotobuf.lib"
echo protobuf_lib_path: %protobuf_lib_path%

set "protobuf_lib_full_path=%~1%protobuf_lib_path%"
echo protobuf_lib_full_path: %protobuf_lib_full_path%

:: Check if protobuf has already been built
if exist "%protobuf_lib_full_path%" (

    echo Library %protobuf_lib_full_path% exists. It will not be rebuilt.

) else (

    echo Library %protobuf_lib_path% not found. Beginning build process...

    @REM Make sure we're in the ProtobufLibrary folder
    cd /d "%~1"

    :: Update submodules (necessary)
    cd protobuf
    git submodule update --init --recursive

    @REM Apply patch for v3.17.1 which was fixed at the below URL
    @REM but didn't get in to protobufs until 3.20.0. Unfortunately,
    @REM the most recent version we can used is tied to BSK's 
    @REM currently or 3.17.1
    git apply ../Protobuf_patch1.patch
    git apply ../Protobuf_patch2.patch

    @REM Link to fix:
    @REM https://github.com/protocolbuffers/protobuf/commit/ef1c9fd9077440acacf4fec112153dda4a2c9d44#diff-d35d85d6ef5be92bdbaa901ca9155566f5d7dc2e4fbf5e4ae6d111a615169959

    @REM Build w/ Cmake
    mkdir compile
    cd compile
    cmake ../cmake -G "Visual Studio 17 2022" -A x64 ^
        -DCMAKE_BUILD_TYPE=Release ^
        -DCMAKE_CXX_STANDARD=14 ^
        -Dprotobuf_BUILD_SHARED_LIBS=ON
    cmake --build . --parallel 8 --config Release

    cd "..\.."
    mkdir include\google
    robocopy "protobuf\src\google" "include\google" /E

    mkdir lib\Release
    robocopy "protobuf\compile\Release" "lib" "libprotobuf.lib"
)
