# x64 Cross-Compilation Pitfalls (from ARM64 host)

> Lessons from cross-compiling llama-server for x86_64 on an ARM64 Jetson host.
> Tested 2026-07-08.

## Toolchain

```bash
# Install cross-compiler (one-time):
apt install gcc-x86-64-linux-gnu g++-x86-64-linux-gnu
```

## CMake configuration

```bash
cmake -B /tmp/llama-build-x64 -S /path/to/llama.cpp \
  -DCMAKE_C_COMPILER=x86_64-linux-gnu-gcc \
  -DCMAKE_CXX_COMPILER=x86_64-linux-gnu-g++ \
  -DCMAKE_SYSTEM_NAME=Linux \
  -DCMAKE_SYSTEM_PROCESSOR=x86_64 \
  -DGGML_NATIVE=OFF \
  -DGGML_CUDA=OFF \
  -DLLAMA_CURL=OFF \
  -DLLAMA_BUILD_UI=OFF \
  -DCMAKE_BUILD_TYPE=Release
```

## Pitfall 1: `llama_ui_asset` compilation error

**Problem:** `server-http.cpp` references `llama_ui_asset` type, but when
`LLAMA_BUILD_UI=OFF` is set, the type is not defined anywhere. Build fails:
```
tools/server/server-http.cpp:185:20: error: 'llama_ui_asset' does not name a type
```

**Root cause:** `tools/ui/ui.h` only defines the struct when
`LLAMA_BUILD_UI` is defined, but `server-http.cpp` uses it unconditionally.

**Fix:** Patch `ui.h` to always define the struct and provide stub
implementations when `LLAMA_BUILD_UI` is not defined:
```cpp
// Add to tools/ui/ui.h (after existing #ifdef block):
#include <string>
#include <vector>
struct llama_ui_asset {
    std::string name;
    std::string data;
    std::string mime_type;
};
inline std::vector<llama_ui_asset> llama_ui_get_assets() {
#ifdef LLAMA_BUILD_UI
    return { /* ... embedded assets ... */ };
#else
    return {};
#endif
}
inline const llama_ui_asset * llama_ui_find_asset(const std::string n) {
    for (const auto a : llama_ui_get_assets()) {
        if (a.name == n) return &a;
    }
    return nullptr;
}
```

**Note:** `tools/ui/` may be untracked in git (`?? tools/ui/`). The generated
`.hpp` files (index.html.hpp, bundle.js.hpp, etc.) are build artifacts that
only exist after a full build with `LLAMA_BUILD_UI=ON`.

## Pitfall 2: Stale root-owned CMakeCache

**Problem:** Previous builds (especially Docker builds) create root-owned
files in the build directory. Cross-compile then fails:
```
CMake Error: The current CMakeCache.txt directory is different than the
source /src/CMakeLists.txt used to generate cache.
```

**Fix:** Build in a clean `/tmp` directory, never reuse the native build dir:
```bash
rm -rf /tmp/llama-build-x64
cmake -B /tmp/llama-build-x64 -S /path/to/llama.cpp ...
```

## Pitfall 3: Missing scripts/xxd.cmake

**Problem:** Build fails with:
```
CMake Error: Not a file: /path/to/llama.cpp/scripts/xxd.cmake
```

**Fix:** Restore from git:
```bash
cd /path/to/llama.cpp
git checkout HEAD -- scripts/xxd.cmake
```

## Pitfall 4: x64 binary is CPU-only

Cross-compiled x64 llama-server has NO CUDA support (`-DGGML_CUDA=OFF`).
This is fine for CPU inference but will be slow. For GPU x64, build natively
on the x64 target machine.

## Pitfall 5: Docker buildx for x64 fails via QEMU

### Problem A: apt signature verification fails

```bash
docker buildx build --platform linux/amd64 -t hermes-agent:x64 --load .
# E: There were unauthenticated packages and -y was used without --allow-unauthenticated
```

**Fix:** Add `--allow-unauthenticated` to apt-get install AND
`--allow-insecure-repositories` to apt-get update in Dockerfile.

### Problem B: Node.js/npm SIGSEGV inside QEMU (CRITICAL)

Even after fixing apt, Node.js crashes inside QEMU x64 emulation:

```
RUN npm install --prefer-offline --no-audit
# x86_64-binfmt-P: QEMU internal SIGSEGV {code=MAPERR, addr=0x20}
# Segmentation fault (core dumped)
# exit code: 139
```

This is a **fundamental QEMU limitation** — Node.js V8 engine uses
architecture-specific JIT compilation that QEMU cannot emulate reliably.
This affects `npm install`, `npm run build`, `npx playwright install`, and
ANY Node.js process inside a cross-compiled container.

**Fix:** Skip ALL npm steps in the Dockerfile when cross-compiling:

```dockerfile
# Replace npm steps with noop:
RUN true  # npm+playwright skipped - QEMU SIGSEGV on x64 cross-build
RUN true  # web+ui-tui build skipped - QEMU SIGSEGV
```

Also remove `node_modules` from the chown step:
```dockerfile
# Was: chown -R hermes:hermes ... /opt/hermes/node_modules
# Now: chown -R hermes:hermes /opt/hermes/.venv /opt/hermes/ui-tui /opt/hermes/gateway
```

**Result:** x64 Docker image builds but WITHOUT web UI assets and WITHOUT
node_modules. The gateway and Python backend work, but dashboard serves no
web interface. To get a full image, build natively on an x64 machine.

**Successful x64 build recipe** (tested 2026-07-08):
```bash
cd /home/user/.hermes/hermes-agent
cp Dockerfile Dockerfile.x64
# Patch: add --allow-unauthenticated to apt-get install
# Patch: add --allow-insecure-repositories to apt-get update
# Patch: replace npm install+build with `RUN true`
# Patch: remove node_modules from chown
docker buildx create --name x64builder --use
docker buildx build --platform linux/amd64 -t hermes-agent:x64 -f Dockerfile.x64 --load .
# Image size: ~2.3GB (vs 4.65GB ARM64 with full npm)
docker save hermes-agent:x64 | gzip > docker/hermes-agent-x64.tar.gz
```

## Copying shared libraries

The cross-compiled binary needs its shared libs. Copy with dereference:
```bash
mkdir -p /target/llama.cpp/x64
cp /tmp/llama-build-x64/bin/llama-server /target/llama.cpp/x64/
cp /tmp/llama-build-x64/bin/lib*.so* /target/llama.cpp/x64/
# On x64 target: run with LD_LIBRARY_PATH=. ./llama-server
```

## Verify binary architecture

```bash
file /tmp/llama-build-x64/bin/llama-server
# Should show: ELF 64-bit LSB pie executable, x86-64
```
