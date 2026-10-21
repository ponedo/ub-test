# Native provenance: no new CS+MC protocol patch

CS+MC adds application code only. It neither patches nor rebuilds the accepted native tree or its loaded libraries. This does **not** mean the native tree is pristine: the experiment inherits the six already-accepted patches below. The WRITE-v2 envelope format, native ACK/response/retry state, windows, allocator policy and credit protocol are unchanged by CS+MC.

## Three distinct revision identities

- Current application baseline: `3a33cc6a249667fc46bf02ac0fed4e1127d7c1ab` in `ponedo/ub-test`.
- Accepted native restoration's historical application anchor: `3521a64fd300938af3af4573a9793c4cde8d9649`, tree `8f50dc4772debb9b8017d0e4e902a5510525c05e`. This is not the native revision.
- Pristine native base: `b8375b51a094d3b1217b697989e1ab979f609e64` in `https://gitcode.com/open-usim/ns-3-ub.git`.

Native restoration accounted for 3,427 pristine files and all 3,430 resulting files after the exact accepted patch chain. That restoration predates CS+MC; its provenance is evidence of the reused dependency, not a new native build performed for this experiment.

## Inherited patch chain, in application order

All paths are relative to the application repository. Each digest is SHA-256.

| Order | Patch | Digest |
|---|---|---|
| 1 | `experiments/ub-multicast-v2/patches/native-write-v2.patch` | `3e478e43258ae78b734a886ee5beae805986e471764599f82442f6de0628bb12` |
| 2 | `experiments/ub-multicast-retransmission/patches/transport-fault-seam.patch` | `80732293d609817d120cf38cfc5f91cb4aa7bc92b6a6f5646205124cbb562f63` |
| 3 | `experiments/ultraep-multicast-integration/patches/peek-original-head.patch` | `51edc0e5e4f5be4d1a56dde0e1d68c572e21b34ffd21d4a1e3c1e1ff8c3b6abd` |
| 4 | `experiments/ultraep-multicast-integration/patches/allocator-revalidation.patch` | `4cd98af20ce1557b3b1820f674a7c5a94f6b54d7a7789f92768da42f79fc1877` |
| 5 | `experiments/multicast-reversal-diagnosis/patches/native-diagnostics.patch` | `0623bf4213ecf142bc8dabbdcf4b766ec417b63f0b17fd2d0c7a9e1566371089` |
| 6 | `experiments/multicast-controlled-ablation/native/ub-jetty-controlled-ablation.patch` | `f04aa181e011c097d35bdc359ca4d294f147f5ae7dc4562204932e287e92d600` |

The final inherited patch changes exactly `src/unified-bus/model/protocol/ub-function.cc`, `ub-function.h` in the same directory, and `src/unified-bus/model/ub-reversal-diagnostic.h` for passive hooks. It does not change the allocator. Accepted allocator SHA-256 is `c841f37a5a8fe80d44a432eb6b76ea88fd9f42fbb285e18db7ff9e2057defe5b`.

## Actual source manifests

There is no invented combined `native-manifest.json`. The accepted source checks use these existing files:

| Manifest | Scope checked | SHA-256 |
|---|---|---|
| `experiments/ultraep-multicast-integration/candidate-native-source-sha256.json` | 109-file integration inventory | `349721cdf1a14455cb14d8bdbfffe259730436fc9769fc3403405b75a09b3909` |
| `experiments/multicast-reversal-diagnosis/native-diagnostic-manifest.json` | 9-file diagnostic manifest | `30cea12a34143be0d2089350e05b77e324ad467939385ae8ac778fbec906fc61` |
| `experiments/multicast-controlled-ablation/native/native-patch-manifest.json` | 12-file controlled-ablation manifest | `adde98e0a6555a956c590f81e8f89828b3bc9c9603965eaa72671bf65705924e` |

Historical application commit fields within these manifests must not be substituted for the pristine native base above. Full restoration evidence additionally records the complete base/candidate inventories and successful check/apply commands for all six patches. Source-manifest equality alone does not establish loaded-library equality: the build and run identities also pin the complete accepted ten-library closure.

The reused `libns3.44-unified-bus.so` SHA-256 is `f9bdef9dff2968e43045eb099c497f790f08e983236ecad57b4d2e9837dda084`. Native defaults remain TA window 512, TP packet window 1,000, Jetty out-of-order ACK window 2,048, and the original allocator.

## New application delta

Only the new experiment directory implements CS+MC. Its `layer.cc` starts from the accepted controlled-ablation application and includes the new `hybrid-multicast.h` and `hybrid-integration.inc`; accepted shared headers are referenced, not edited. The separate selector `--weight-transport=cs-mc` requires original CS graph kind 2. Default `--weight-transport=original` preserves the old paths, including the already-multicast graph kind 4.

The APP proxy makes an immediate, full-fixed-group merge decision on an already-selected native head. Ineligible merges fall back immediately to that native unicast. It adds offset-aware lazy codec bookkeeping, per-member original-send coverage, bounded hybrid diagnostics and exact lifecycle checks, not an admission queue, reservation system, ACK state machine or transport protocol. See `RUNTIME-SAFETY.md` for the boundary.

Recorded accepted CS+MC binary SHA-256: `2fd21591e56bf8bd9dfe7ee481e5ce935ac776722ba1e3193acb38ee0d6e5b2f`. Its build provenance records `app_only=true`, `native_rebuilt=false`, build-plan digest `ddd2dd242d75800db545d549dddd643055ee0eb336d302aa1f43d131680b2873` and runtime-identity digest `d9af515501e22798d7b93d00fa66c2495637dcf51cfaf1266203f234a9f3d905`.

The recorded APP compiler was Debian c++ 14.2.0 with `-std=c++20 -O2 -g`. The executable uses `--disable-new-dtags` and a recorded absolute native-library RPATH. Moving the executable alone is not a valid reproduction. A clean APP build must pin the actual accepted native artifacts and produce a fresh identity; it is not promised to reproduce the old binary byte-for-byte at another path or with another toolchain.
