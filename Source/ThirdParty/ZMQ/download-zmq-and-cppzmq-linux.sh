#!/bin/bash
echo ${PWD}
echo "Relative path ${1}"

zmq_git_tag="v4.2.5"
zmq_lib_path="libzmq/build/lib/libzmq.a"
zmq_include_path="libzmq/include"
echo "zmq_lib_path: ${zmq_lib_path}"
zmq_lib_full_path="${1}${zmq_lib_path}"
echo "zmq_lib_full_path: ${zmq_lib_full_path}"

if [ -f $zmq_lib_full_path ]; then
  echo "ZMQ will not be rebuilt. Library ${zmq_lib_full_path} exists."
else
  echo "ZMQ will be built. Library ${zmq_lib_full_path} not found."

  zmq_git_repo="https://github.com/zeromq/libzmq.git"
  echo "Cloning Zmq ${zmq_git_tag} from ${zmq_git_repo}."
  # Change dir from current working to build destination path
  cd ${1}
  git clone -b $zmq_git_tag $zmq_git_repo
  cd libzmq
  git submodule update --init --recursive
  
  # CMake Build 
  echo "Building libzmq"
  mkdir build
  cd build
  env
  cmake ..
  make -j4
fi

cppzmq_git_tag="v4.5.0"
cppzmq_directory_name="cppzmq"

if [ -d $cppzmq_directory_name ]; then
  echo "CPPZMQ will not be cloned. Directory ${cppzmq_directory_name} exists."
else
  cppzmq_git_repo="https://github.com/zeromq/cppzmq.git"
  echo "Cloning Cppzmq ${cppzmq_git_tag} from ${cppzmq_git_repo}."
  # Change dir from current working to build destination path
  cd ${1}
  git clone -b $cppzmq_git_tag $cppzmq_git_repo
  cd $cppzmq_directory_name
  git submodule update --init --recursive
  
  # CMake Build 
  echo "Building cppzmq"
  mkdir build
  cd build
  cmake .. -DZeroMQ_STATIC_LIBRARY=$zmq_lib_full_path -DCMAKE_INCLUDE_PATH=$zmq_include_path -DCPPZMQ_BUILD_TESTS=OFF
  make -j4
fi
