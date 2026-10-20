# Multicast WRITE v2

Experimental Tag-free wire envelope, with switch-side reconstruction of independent native RTP WRITE packets. Historical v1 and oracle modes remain in their original files, unchanged. Start with [AUDIT.md](AUDIT.md), [FORMAT.md](FORMAT.md) and [REPORT.md](REPORT.md).

Delivered native changes are in [patches/native-write-v2.patch](patches/native-write-v2.patch). The source adapter is [adapter-v2.h](adapter-v2.h); receiver nodes require no multicast parser. This is a no-loss, single-switch simulator extension, not a UB-standard or hardware multicast implementation.

## Reconstruct and reproduce

Use a disposable clone from `https://gitcode.com/open-usim/ns-3-ub.git`, checkout exactly `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`. Apply these existing project patches in order:

1. `../ub-network-multicast-poc/patches/accepted-unicast-baseline.patch`
2. `../ub-network-multicast-poc/patches/network-replication.patch`
3. `../ub-lightweight-multicast-adapter/patches/lightweight-adapter.patch`

All108 accepted source hashes must match `../ub-multicast-fanout-header/native-source-sha256.json`. The reproduction script checks them before applying v2. It does not accept an already modified v2 tree. Requires C++20, CMake/Ninja, Python3+psutil and OpenSSL development library for the old pair-layer regression. Use the installed CMake, Ninja and C++20 toolchain; exact executed commands and resource results are recorded. Compilation and runs remain sequential, at most-j2 per native build, with the existing unchanged guard.

```sh
bash experiments/ub-multicast-v2/reproduce.sh /path/to/accepted-native /path/to/fresh-private-output
```

The tools submodule/parser was absent in the original dot cloud host and remains an explicitly reported original examples-suite limitation. Do not silently rewrite that failure into success. No large UltraEP experiment or optional18MiB point is run. The old four-strategy regression uses its existing small synthetic model and64 assignments, not real Qwen scaling.

Focused commands for an already patched and built native tree:

```sh
python3 experiments/ub-multicast-v2/build.py --native "$NATIVE" --out "$PRIVATE/fixtures"
python3 experiments/ub-multicast-v2/run.py --build "$PRIVATE/fixtures" --out "$PRIVATE/matrix"
python3 experiments/ub-multicast-v2/regress.py --native "$NATIVE" --out "$PRIVATE/regressions"
```

Do not reuse output directories. Each failed build and expected negative case retains its own logs and resource status. Public results contain summaries, packet/port/target counts and hashes; raw received payloads and full traces stay private. `results/patch-replay.json` verifies exact source reconstruction. Default CBFC can retain a few batched, not-yet-sent credit cells; conservation includes those cells. The pressure case uses the original small-queue fixture's return threshold1 and verifies full credit return. No buffer or association leak is tolerated.
