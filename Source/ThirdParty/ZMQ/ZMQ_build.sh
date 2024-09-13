#!/bin/tcsh -f
echo "Current working directory -> ${cwd}"
echo "Relative path ->  ${1}"

set zmq_lib_path = "libzmq_build/lib/libzmq.a"
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
    cd ..
    mkdir libzmq_build
    cd libzmq_build
    env
    cmake ../libzmq
    make -j4

    cd ..

    # Do all of that for cppZMQ
    cd cppzmq
    git submodule update --init --recursive

    # CMake Build 
    echo "Building cppzmq..."
    cd ..
    mkdir cppzmq_build
    cd cppzmq_build
    cmake ../cppzmq -DZeroMQ_STATIC_LIBRARY=$zmq_lib_full_path -DCMAKE_INCLUDE_PATH=../libzmq/include -DCPPZMQ_BUILD_TESTS=OFF
    make -j4
    
endif
