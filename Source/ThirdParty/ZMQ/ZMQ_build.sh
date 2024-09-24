#!/bin/tcsh -f
echo "Current working directory -> ${cwd}"
echo "Relative path ->  ${1}"

set zmq_lib_path = "libzmq/build/lib/libzmq.a"
echo "zmq_lib_path: ${zmq_lib_path}"

set zmq_lib_full_path = ${1}${zmq_lib_path}
echo "zmq_lib_full_path: ${zmq_lib_full_path}"

if ( -f $zmq_lib_full_path ) then
  echo "ZMQ will not be rebuilt. Library ${zmq_lib_full_path} exists."
else
    echo "ZMQ will be built. Library ${zmq_lib_full_path} not found."

    # Make sure we're in the ZMQ folder
    cd ${1}

    cd libzmq
    git submodule update --init --recursive

    # CMake Build 
    echo "Building libzmq..."
    mkdir build
    cd build
    env
    cmake ..
    make -j4

    cd ../..

    # Do all of that for cppZMQ
    cd cppzmq
    git submodule update --init --recursive

    # CMake Build 
    echo "Building cppzmq..."
    mkdir build
    cd build
    cmake ..
    make -j4
    
endif
