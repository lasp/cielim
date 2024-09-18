@echo off
echo Current working directory: %CD%
echo Relative path: %~1

:: Path from build directory to libopencv_world library file
set "opencv_lib_path=opencv\build\lib\Release\opencv_world4100.lib"
echo opencv_lib_path: %opencv_lib_path%

set "opencv_lib_full_path=%~1%opencv_lib_path%"
echo opencv_lib_full_path: %opencv_lib_full_path%

:: Check if OpenCV has already been built
if exist "%opencv_lib_full_path%" (

    echo OpenCV will not be rebuilt. Library %opencv_lib_full_path% exists.

) else (

    echo OpenCV will be built. Library %opencv_lib_full_path% not found.
    
    @REM Make sure we're in the OpenCV folder
    cd /d "%~1"

    @REM CMake Build
    echo Building OpenCV...
    cd opencv
    mkdir build
    cd build
    cmake .. -G "MinGW Makefiles" ^
        -DCMAKE_BUILD_TYPE=Release ^
        -DBUILD_PERF_TESTS:BOOL=OFF ^
        -DBUILD_TESTS:BOOL=OFF ^
        -DBUILD_DOCS:BOOL=OFF ^
        -DWITH_CUDA:BOOL=OFF ^
        -DBUILD_EXAMPLES:BOOL=OFF ^
        -DINSTALL_CREATE_DISTRIB=ON ^
        -DOPENCV_EXTRA_MODULES_PATH=..\..\opencv_contrib\modules
    cmake --build . --parallel 8 --config Release
)
