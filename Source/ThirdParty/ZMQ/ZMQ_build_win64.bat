@echo off
echo Current working directory: %CD%
echo Relative path: %~1

:: Path from build directory to libzmq library file
set "zmq_lib_path=libzmq\build\lib\Release\libzmq-v143-mt-4_3_6.lib"
echo zmq_lib_path: %zmq_lib_path%

set "zmq_lib_full_path=%~1%zmq_lib_path%"
echo zmq_lib_full_path: %zmq_lib_full_path%

:: Check if ZMQ has already been built
if exist "%zmq_lib_full_path%" (

    echo ZMQ will not be rebuilt. Library %zmq_lib_full_path% exists.'

) else (

    echo ZMQ will be built. Library %zmq_lib_full_path% not found.

    @REM Make sure we're in the ZMQ folder
    cd /d "%~1"

    cd libzmq
    git submodule update --init --recursive

    @REM CMake Build 
    echo Building libzmq...
    mkdir build
    cd build
    env
    cmake .. -G "Visual Studio 17 2022" -A x64 -DCMAKE_BUILD_TYPE=Release
    cmake --build . --parallel 8 --config Release

    cd "..\.."

    @REM Do all of that for cppZMQ
    cd cppzmq
    git submodule update --init --recursive

    @REM CMake Build 
    echo Building cppzmq...
    mkdir build
    cd build
    cmake .. -G "Visual Studio 17 2022" -A x64 -DCMAKE_BUILD_TYPE=Release
    cmake --build . --parallel 8 --config Release
)
