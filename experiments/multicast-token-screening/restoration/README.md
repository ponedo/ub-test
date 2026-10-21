# Accepted runtime restoration for the 256-token screening

This is a compact, portable record of a necessary restoration, not a new model or
protocol implementation. The requested latest accepted executable was absent from
the restored workspace snapshot. Older control binaries were not substituted or
modified. Existing matching binaries should still be preferred when available.

The restored application is pinned to
[`3521a64fd300938af3af4573a9793c4cde8d9649`](https://github.com/ponedo/ub-test/tree/3521a64fd300938af3af4573a9793c4cde8d9649),
with source tree `8f50dc4772debb9b8017d0e4e902a5510525c05e`. All 10,977 accepted
blob files were verified. The native base is
`b8375b51a094d3b1217b697989e1ab979f609e64` from
[OpenUSim](https://gitcode.com/open-usim/ns-3-ub). The exact six-patch chain and
all hashes are listed in `provenance.json`.

The native allocator is unchanged from the accepted diagnostic tree. Runtime
defaults remain TA window 512, TP packet window 1000, and ACK bitmap 2048. No
optimization, default promotion, formal simulation, or parameter sweep is part of
this restoration. Historical executable byte equality is not claimed: a new build
has its own compiler, path-dependent binary, and native-library identities.

## Contents and evidence limits

- `restore-native.py`, `build-runtime.py`, and `test-runtime.py` are byte-for-byte
  copies of the private helpers actually used. Their workspace discovery is
  relative to their installed location; no private workspace identifier is embedded.
- `build-native.py` is an unchanged copy of the accepted native build driver. It
  is provided for review; invoke the original file in the accepted source checkout
  because its imports are relative to that checkout.
- `helper-validation.json` records identical-file checks and syntax-only parsing.
  Staging did not execute these helpers, rebuild, or simulate anything.
- `commands-normalized.json` preserves recorded command argument ordering and
  flags, replacing only private path prefixes with portable placeholders.
- `resources.json` retains actual wall time, child user/system CPU, kernel peak
  RSS, sampled process-tree peak RSS, exit status, and unchanged resource limits.
- `provenance.json` binds the original private source/native/build/unit manifests
  by SHA256, without publishing their 4,005 absolute-path entries, host details,
  raw workload inputs, or full native hash inventories. Public accepted-source
  references and compact binary hashes are included.

## Prerequisites

Use a fresh workspace and preserve all existing control trees. Required installed
tools are Python 3 with `psutil`, Git, C++20-capable `c++`, CMake, and Ninja. The
recorded toolchain was Debian GCC 14.2.0, CMake 4.4.4, and Ninja
1.13.2.git.kitware.jobserver-pipe-1. Do not install or change tools merely to run
this review package. For a separately authorized restoration, use already installed
matching tools or the existing accepted `real-batch-build-tools` directory.

The guard is imported unchanged from the accepted checkout. Every native stage
keeps a 4,800-second wall cap, 6 GiB process-tree RSS cap, 7 GiB address-space cap,
1 GiB host-memory reserve, 8 GiB free output disk, and 2 GiB free temporary disk.
Application builds and unit stages use the same memory/disk guards with an
1,800-second wall cap. Native compilation is limited to the unified-bus target
and two compiler jobs. Never run simultaneous builds or relax these guards.

## Fresh-workspace recipe

These commands describe a separately authorized restoration. They were not run
again during publication preparation. Do not run them in the active screening
workspace or over any existing build, result, or control directory.

1. Place a verified checkout of the accepted application commit at
   `<workspace>/token-screen-work`. Create a clean, separate native clone at
   `<workspace>/token-screen-native` and check out the native base above. A clone
   of a local base repository is sufficient; do not copy another tree's build or
   cache artifacts. Confirm that the native working tree is clean.
2. Create `<workspace>/token-screen-private/restoration` and install exactly the
   three helper files `restore-native.py`, `build-runtime.py`, and
   `test-runtime.py` there. The helpers infer `<workspace>` from that location.
3. Supply `remote-tree.json` and `verification.json` in that restoration directory
   from a complete verification of the accepted application source. The source
   tree JSON must contain the pinned tree SHA and the accepted blob entries with
   `path`, `type`, and Git `sha` fields. `verification.json` must record the accepted
   commit/tree and a successful full source check. Do not fabricate these records
   or use a different tree.

For a complete Git checkout, the following read-only source check can produce
those two local provenance inputs. It writes only the new restoration metadata;
it does not change source or invoke a compiler. Run it from `<workspace>` after
installing the helper copies:

```sh
python3 - <<'PY'
import hashlib, json, subprocess
from pathlib import Path
w = Path('token-screen-work')
o = Path('token-screen-private/restoration')
def git(*args):
    return subprocess.check_output(['git', '-C', str(w), *args])
commit = git('rev-parse', 'HEAD').decode().strip()
tree = git('rev-parse', 'HEAD^{tree}').decode().strip()
assert commit == '3521a64fd300938af3af4573a9793c4cde8d9649'
assert tree == '8f50dc4772debb9b8017d0e4e902a5510525c05e'
entries = []
for record in git('ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
    if not record:
        continue
    meta, name = record.split(b'\t', 1)
    mode, kind, digest = meta.decode().split()
    if kind != 'blob':
        continue
    path = name.decode()
    data = (w / path).read_bytes()
    actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    assert actual == digest, path
    entries.append(dict(path=path, type=kind, sha=digest, size=len(data)))
assert len(entries) == 10977
payloads = {
    'remote-tree.json': dict(sha=tree, tree=entries),
    'verification.json': dict(status='PASS', accepted_commit=commit, tree=tree,
        verified_files=len(entries), transport='Pinned Git checkout; all blobs verified'),
}
for name, payload in payloads.items():
    path = o / name
    assert not path.exists(), path
    path.write_text(json.dumps(payload, indent=2) + '\n')
PY
```

4. From `<workspace>`, apply and verify exactly the six accepted patches:

```sh
python3 token-screen-private/restoration/restore-native.py
```

The helper checks the clean native base, applies each patch only after a forward
check, verifies the 109-entry integration manifest, nine diagnostic hashes, and
12 controlled-ablation/unchanged-control hashes. It also accounts for the full
3,430-file final native inventory and verifies that the last patch changes exactly
three allowed passive-observation files while preserving the allocator hash.

5. Run the unchanged accepted native build driver. Omit `--tools` only when
   equivalent CMake/Ninja are already on PATH:

```sh
python3 token-screen-work/experiments/multicast-controlled-ablation/build-native.py \
  --native token-screen-native \
  --out token-screen-private/native-build \
  --tools real-batch-build-tools
```

This configures release mode with assertions ON, logging OFF, native CPU-specific
optimizations OFF, and builds only `unified-bus` with `-j2`. The precise configure
arguments and recorded native compiler flags are in the JSON evidence.

6. Build the accepted application and minimal helpers, then execute the four
   approved existing unit gates:

```sh
python3 token-screen-private/restoration/build-runtime.py
python3 token-screen-private/restoration/test-runtime.py
```

Application compilation preserves `-std=c++20 -O2 -g`, the four accepted ns-3
library link flags, `--disable-new-dtags`, and an absolute RPATH to this fresh
workspace's native `build/lib` directory. Do not move a binary independently of
its native libraries and identity manifest. Only missing historical-binary
prerequisites and workspace paths are adapted; accepted runtime source and guard
implementations are unchanged.

The units are the FIFO observer, native Jetty capacity/ACK boundary, Jetty
observer, and independent roofline model oracle. All four passed in the recorded
restoration. The native unit checks 512/1024/2048 capacity boundaries without
`Simulator::Run`; this is not a token-count or window experiment. The model oracle
passed 16 positive and six negative cases. No extra numerical simulation cases,
real workload runs, or formal screening are launched by this recipe.

The helpers refuse existing fresh-build/output directories and recheck source and
binary identities before/after validation stages. Native patch application assumes
a pristine base and must not be repeated on an already patched tree. If any
identity, guard, command, or unit fails, stop rather than substituting an old
runtime or weakening the gate.
