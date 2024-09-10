#!/bin/tcsh -f
echo "Current working directory -> ${cwd}"
echo "Relative path -> ${1}"

set protobuf_lib_path = "protobuf/src/.libs/libprotobuf.a"
echo "protobuf_lib_path: ${protobuf_lib_path}"

set protobuf_lib_full_path = ${1}${protobuf_lib_path}
echo "protobuf_lib_full_path: ${protobuf_lib_full_path}"

# Check if protobuf has already been built

if ( -f $protobuf_lib_full_path ) then
    echo "Library ${protobuf_lib_full_path} exists. It will not be rebuilt."
else
    echo "Library ${protobuf_lib_path} not found. Beginning build process..."

    # Make sure we're in the ProtobufLibrary folder
    cd ${1}

    # Update submodules (necessary)
    cd protobuf
    git submodule update --init --recursive

    # Apply patch for v3.17.1 which was fixed at the below URL
    # but didn't get in to protobufs until 3.20.0. Unfortunately,
    # the most recent version we can used is tied to BSK's 
    # currently or 3.17.1
    git apply ../Protobuf_patch1.patch
    git apply ../Protobuf_patch2.patch

    # Link to fix:
    # https://github.com/protocolbuffers/protobuf/commit/ef1c9fd9077440acacf4fec112153dda4a2c9d44#diff-d35d85d6ef5be92bdbaa901ca9155566f5d7dc2e4fbf5e4ae6d111a615169959

    # AutoMake Build 
    echo "Building ptotobuf..."
    ./autogen.sh
    ./configure
    make -j8

    # Run checks (Not necessary)
    # make check

    cd ..

    # Copy necessary includes to dedicated include folder
    rm -rf include/google
    mkdir -p include/google
    cp -r protobuf/src/google/ include/google

    # Copy necessary libraries to dedicated lib folder
    rm -rf lib
    mkdir -p lib
    cp protobuf/src/.libs/libprotobuf.a lib


    # In case of upgrade to Cmake, use this ---------------
    # -----------------------------------------------------
    # Create build directory
    # cd ..
    # mkdir -p build

    # Build w/ Cmake
    # cd build
    # cmake ../protobuf/ -D CMAKE_CXX_STANDARD=14
    # cmake --build . --parallel 8
    # sudo cmake --install .

    # cd ..
    # mkdir -p include/google
    # cp -r protobuf/src/google/ include/google
    # cp -r protobuf/third_party/abseil-cpp/absl include/absl

    # mkdir -p lib/Release
    # cp build/libprotobuf.a lib

endif
