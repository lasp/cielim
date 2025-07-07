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
    cmake .. -G "Visual Studio 17 2022" -A x64 ^
        -D BUILD_DOCS:BOOL=OFF  ^
        -D BUILD_EXAMPLES:BOOL=OFF ^
        -D BUILD_opencv_python:BOOL=OFF ^
        -D BUILD_PERF_TESTS:BOOL=OFF ^
        -D BUILD_TESTS:BOOL=OFF ^
        -D CMAKE_BUILD_TYPE=Release ^
        -D CMAKE_INSTALL_PREFIX=.. ^
        -D INSTALL_CREATE_DISTRIB=ON ^
        -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib/modules \
        -D WITH_CUDA:BOOL=OFF ^
        -D WITH_FFMPEG=OFF ^
        -D WITH_GSTREAMER:BOOL=OFF ^
        -D WITH_IPP=OFF ^
        -D WITH_OPENEXR:BOOL=OFF ^
        -D WITH_TESSERACT:BOOL=OFF ^
        -D WITH_VTK:BOOL=OFF 
    cmake --build . --parallel 8 --config Release

    @REM You need to install here or else headers won't all be in the same place
    cmake --install .
)
