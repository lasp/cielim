#!/bin/bash
echo $PWD
echo "Relative path $1"

opencv_version="4.5.5"
opencv_lib_path="lib/libopencv_core.dylib"
echo "opencv_lib_path: $opencv_lib_path"
opencv_lib_full_path="${1}${opencv_lib_path}"
echo "opencv_lib_full_path: $opencv_lib_full_path"

if [ -f "$opencv_lib_full_path" ]; then
  echo "OpenCV will not be rebuilt. Library $opencv_lib_full_path exists."
else
  echo "OpenCV will be built. Library $opencv_lib_full_path not found."

  # Change dir from current working to build destination path
  cd "$1" || exit
  curl -Lo opencv.zip https://github.com/opencv/opencv/archive/${opencv_version}.zip
  curl -Lo opencv_contrib.zip https://github.com/opencv/opencv_contrib/archive/${opencv_version}.zip
  rm -r opencv-${opencv_version}
  unzip opencv.zip
  rm -r opencv_contrib-${opencv_version}
  unzip opencv_contrib.zip
  
  # CMake Build
  echo "Building OpenCV"
  cd opencv-${opencv_version} || exit
  mkdir -p build
  cd build || exit
  cmake ../ \
    -D CMAKE_INSTALL_PREFIX=../../ \
    -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib-${opencv_version}/modules \
    -D BUILD_EXAMPLES=OFF \
    -D BUILD_PERF_TESTS=OFF \
    -D BUILD_TESTS=OFF \
    -D BUILD_opencv_apps=OFF \
    -D BUILD_opencv_calib3d=OFF \
    -D BUILD_opencv_dnn=OFF \
    -D BUILD_opencv_face=OFF \
    -D BUILD_opencv_gapi=OFF \
    -D BUILD_opencv_ml=OFF \
    -D BUILD_opencv_photo=OFF \
    -D BUILD_opencv_python2=OFF \
    -D BUILD_opencv_python3=OFF \
    -D BUILD_opencv_STEREO=OFF \
    -D BUILD_opencv_stitching=OFF \
    -D BUILD_opencv_tracking=OFF \
    -D WITH_OPENEXR=OFF \
    -D BUILD_ZLIB=OFF
  cmake --build . --parallel 8
  cmake --install . 
fi
