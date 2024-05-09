#!/bin/tcsh -f
echo ${cwd}
echo "Relative path ${1}"

set opencv_version = "4.5.5"
set opencv_lib_path = "lib/libopencv_core.dylib"
echo "opencv_lib_path: ${opencv_lib_path}"
set opencv_lib_full_path = ${1}${opencv_lib_path}
echo "opencv_lib_full_path: ${opencv_lib_full_path}"

if ( -f $opencv_lib_full_path ) then
  echo "OpenCV will not be rebuilt. Library ${opencv_lib_full_path} exists."
else
  echo "OpenCV will be built. Library ${opencv_lib_full_path} not found."

  # Change dir from current working to build destination path
  cd ${1}
  curl -Lo opencv.zip https://github.com/opencv/opencv/archive/${opencv_version}.zip
  curl -Lo opencv_contrib.zip https://github.com/opencv/opencv_contrib/archive/${opencv_version}.zip
  rm -r opencv-${opencv_version}
  unzip opencv.zip
  rm -r opencv_contrib-${opencv_version}
  unzip opencv_contrib.zip
  
  # CMake Build
  echo "Building OpenCV"
  cd opencv-${opencv_version}
  mkdir -p build
  cd build
  cmake ../ -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib-${opencv_version}/modules -D CMAKE_INSTALL_PREFIX=../../
  cmake --build . --parallel 8
  cmake --install . 
endif
