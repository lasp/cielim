#!/bin/tcsh -f
echo "Current working directory -> ${cwd}"
echo "Relative path -> ${1}"

# Path from build directory to libopencv_world library file
set opencv_lib_path = "opencv/build/lib/libopencv_world.dylib"
echo "opencv_lib_path: ${opencv_lib_path}"

set opencv_lib_full_path = ${1}${opencv_lib_path}
echo "opencv_lib_full_path: ${opencv_lib_full_path}"

# Check if OpenCV has already been built
if ( -f $opencv_lib_full_path ) then
  echo "OpenCV will not be rebuilt. Library ${opencv_lib_full_path} exists."
else
  echo "OpenCV will be built. Library ${opencv_lib_full_path} not found."
  
  # Make sure we're in the OpenCV folder
  cd ${1}

  # CMake Build
  echo "Building OpenCV..."
  cd opencv
  mkdir build
  cd build
  cmake .. \
    -D BUILD_PERF_TESTS:BOOL=OFF \
    -D BUILD_TESTS:BOOL=OFF \
    -D BUILD_DOCS:BOOL=OFF  \
    -D WITH_CUDA:BOOL=OFF \
    -D BUILD_EXAMPLES:BOOL=OFF \
    -D INSTALL_CREATE_DISTRIB=ON \
    -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib/modules \
    -D CMAKE_INSTALL_PREFIX=..
  cmake --build . --parallel 8

  # You need to install here or else headers won't all be in the same place
  cmake --install .
endif
