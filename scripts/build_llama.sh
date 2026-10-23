#!/bin/sh
# Build llama.cpp (llama-server + llama-bench) into <repo>/binaries/linux-*.
# Requires: git, cmake, a C/C++ toolchain. --vulkan also needs glslang + Vulkan SDK.
set -e
cd "$(dirname "$0")/.."
TAG=${1:-$(curl -s https://api.github.com/repos/ggml-org/llama.cpp/releases/latest | sed -n 's/.*"tag_name": "\(b[0-9]*\)".*/\1/p')}
[ -n "$TAG" ] || TAG=master
echo "building llama.cpp $TAG"
git clone --depth 1 --branch "$TAG" https://github.com/ggml-org/llama.cpp .llama-build
cmake -S .llama-build -B .llama-build/build -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF -DGGML_NATIVE=OFF
cmake --build .llama-build/build -j"$(nproc)" --target llama-server llama-bench
mkdir -p binaries/linux-x86_64
cp .llama-build/build/bin/llama-server .llama-build/build/bin/llama-bench binaries/linux-x86_64/
cp -n .llama-build/build/ggml/base/*.so binaries/linux-x86_64/ 2>/dev/null || true
cp -n .llama-build/build/ggml/libggml-base.so binaries/linux-x86_64/ 2>/dev/null || true
find .llama-build/build -name "libggml*.so*" -exec cp -n {} binaries/linux-x86_64/ \; 2>/dev/null || true
if [ "${VULKAN:-0}" = "1" ]; then
  cmake -S .llama-build -B .llama-build/build-vk -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF -DGGML_NATIVE=OFF
  cmake --build .llama-build/build-vk -j"$(nproc)" --target llama-server llama-bench
  mkdir -p binaries/linux-vulkan
  cp .llama-build/build-vk/bin/llama-server .llama-build/build-vk/bin/llama-bench binaries/linux-vulkan/
  find .llama-build/build-vk -name "libggml*.so*" -exec cp -n {} binaries/linux-vulkan/ \;
fi
rm -rf .llama-build
echo "done: binaries/linux-x86_64 $( [ "${VULKAN:-0}" = "1" ] && echo + binaries/linux-vulkan )"
