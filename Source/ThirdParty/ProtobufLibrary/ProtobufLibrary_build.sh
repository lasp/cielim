#!/bin/tcsh -f
echo "Current working directory -> ${cwd}"
echo "Relative path -> ${1}"

set protobuf_lib_path = "build/libprotobuf.a"
echo "protobuf_lib_path: ${protobuf_lib_path}"

set protobuf_lib_full_path = ${1}${protobuf_lib_path}
echo "protobuf_lib_full_path: ${protobuf_lib_full_path}"

# Check if protobuf has already been built

if ( -f $protobuf_lib_full_path ) then
    echo "Library ${protobuf_lib_full_path} exists. It will not be rebuilt."
else
    echo "Library ${protobuf_lib_path} not found. Beginning build process..."

    # Update submodules (necessary)
    cd protobuf
    git submodule update --init --recursive

    # Create build directory
    cd ..
    mkdir -p build

    # Build w/ Cmake
    cd build
    cmake ../protobuf/ -D CMAKE_CXX_STANDARD=14
    cmake --build . --parallel 8
    sudo cmake --install .

    cd ..
    mkdir -p include/google
    cp -r protobuf/src/google/ include/google

    mkdir -p lib/Release
    cp protobuf/build/libprotobuf.a lib

endif
