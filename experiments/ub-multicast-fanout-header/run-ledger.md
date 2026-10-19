# Execution ledger

All commands were run on the existing dot cloud host, sequentially. The native source tree remained pinned and unchanged. Compiler flags were C++20 -O3 -g; no -O0 performance runs.

The generic ns-3-ub-tools submodule scripts are absent in this checkout. This experiment uses the already-built native library and the accepted standalone C++ application path; it does not claim the generic launcher/tooling startup is complete.

| UTC checkpoint | Actual result |
|---|---|
|2026-10-19 11:42|Controlled matrix and predictions recorded before execution.|
|11:49|Current fanout and production regression executables built successfully.|
|11:50|Header codec:3 positive and36 intentional-rejection cases passed.|
|11:52|Legacy-header executable built;25 small native simulations and independent checks passed.|
|11:53|4 legacy/current Debug pairs matched byte-for-byte;17 payload/completion/relay faults rejected as expected.|
|11:54|Frozen independent verifier rechecked33 actual cases;20 main 18MiB cases started.|
|12:20|All20 main cases and postflights passed. No protected stop or simulator retry.|
|12:24|All5 supplemental ideal-Oracle cases and postflights passed.|
|12:25|All21 pressure/window/feedback cases passed (12 positive,9 expected rejections). Old regressions started.|

[Per-case final status](results/run-status.csv) and [per-stage start, wall/CPU time, RSS, return code and guard result](results/host-resources.csv) retain the actual matrix outcomes. Exact command templates are in command-manifest.yaml and executable scripts. Runtime-specific absolute paths and bulky diagnostic evidence stay private.

Main guards:3600 seconds per stage,6GiB RSS,7GiB address space,min8GiB disk,min2GiB temporary space,min1.5GiB available host memory. Negative tests are deliberate nonzero exits and are not resource-protection failures.

2026-10-19 12:29 UTC: old application, singleton, multicast and network regressions completed. Native suites 48/49: the known missing-parser examples-suite failure remains explicitly qualified. The frozen independent verifier passed all38 unit/mutation tests again under the resource guard. Publication acceptance requires remote branch, sole-parent commit, complete tree and byte-exact file verification; delivery is withheld until those checks complete.
