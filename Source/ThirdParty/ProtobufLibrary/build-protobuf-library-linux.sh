#!/bin/bash
echo $PWD
echo "Relative path $1"

git_tag="v3.17.1"
protobuf_lib_path="lib/libprotobuf.a"
echo "protobuf_lib_path: $protobuf_lib_path"
protobuf_lib_full_path="$1$protobuf_lib_path"
echo "protobuf_lib_full_path: $protobuf_lib_full_path"
protobuf_git_repo="https://github.com/protocolbuffers/protobuf.git"
if [ -f "$protobuf_lib_full_path" ]; then
    echo "Library $protobuf_lib_full_path exists. It will not be rebuilt."
    exit
fi

echo "Library $protobuf_lib_path not found."

echo "Cloning protobufs $git_tag from $protobuf_git_repo."
# Change dir from current working to build destination path
cd "$1" || exit
git clone -b $git_tag $protobuf_git_repo
cd protobuf || exit
git submodule update --init --recursive

# Apply patch for v3.17.1 which was fixed at the below URL
# but didn't get in to protobufs until 3.20.0. Unfortunately,
# the most recent version we can use is tied to basilisk 
# currently or 3.17.1
# https://github.com/protocolbuffers/protobuf/commit/ef1c9fd9077440acacf4fec112153dda4a2c9d44#diff-d35d85d6ef5be92bdbaa901ca9155566f5d7dc2e4fbf5e4ae6d111a615169959
git apply ../src_google_protobuf_port_undef_inc_3_17_1.patch
git apply ../src_google_protobuf_port_def_inc_3_17_1.patch

# AutoMake Build 
echo "Building protobuf."
./autogen.sh
./configure
make -j8
make check

cd ..
rm -rf include
mkdir -p include/google
cp -r protobuf/src/google include/google

rm -rf lib
mkdir -p lib
cp protobuf/src/.libs/libprotobuf.a lib

# Later versions of protobuf move from automake to CMake and the below
# works for the later protobuf versions. If we upgrade then we can use
# the below.

# CMake Build
# Working from the directory above the "protobuf" repo directory
# cd ..
# mkdir protobuf/build
# cmake -G "Ninja Multi-Config" -S protobuf -B protobuf/build -D CMAKE_CXX_STANDARD=14
# cmake --build protobuf/build --config Release

# rm -rf include
# mkdir -p include/google
# cp -r protobuf/src/google/ include/google

# rm -rf lib
# mkdir -p lib/Release
# cp protobuf/build/Release/libprotobuf.a lib
