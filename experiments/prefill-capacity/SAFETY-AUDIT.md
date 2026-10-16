# Capacity boundary audit (pinned native source)

Native ns-3-ub: d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b. Base application: 555f2a591d7537b35fb507078dd686a50fb3400e. No protocol changes or memory optimizations are authorized here.

## Admission versus actual resource cost

Old relay admission: T<=100000; A=T*k<=100000; checked payload 2*A*H*d+R*W<=256MiB; W<=64MiB; physical instances<=1024; weight tasks<=20000. These are software rejection conditions, not evidence of OOM. At k8 the requested T values are 6250,12500,25000,62500,125000; the last also violates old T admission.

`AddTransfer` retains all dispatch/combine/weight buffers and `weightData` separately retains W per replica: persistent application payload is 2*A*H*d+2*R*W (tree transfer volume R*W), before send/receive vectors, explicit packet payload copies, metadata, native objects, trace buffers or Python JSON. The 256MiB expression is not total host memory.

A native Jetty is created per remote task before running and retained by the manager. `ub-function.h:447` owns an ACK window; `ub-function.cc:1020-1044` gives threshold2048 and initializes it. `model/ub-sliding-bitmap-window.h:20-23,103` stores **2048 uint64_t slots**, not 2048 packed bits: **16KiB per Jetty for this window alone**. Thus 100000 remote tasks need 1.526GiB, and 1000000 need 15.259GiB just for this window. This is a source-derived allocation floor, not a measured RSS or a full allocator estimate. The fixed workload's actual remote-task count must be used. Window size, Jetty lifetime and submission timing stay unchanged.

## Wire and integer bounds

`protocol/ub-header.cc:1639-1641` masks request Jetty IDs with `0xFFFFF`; ACK at 2868-2870 uses the same 20-bit mask. Deserialization reconstructs high4+low16 bits. The 24-bit comment in `ub-function.h` is not authoritative for wire behavior. The executor uses global task ID as Jetty number. Require remote task ID <=1048575; conservative preflight: **2*A+weight_tasks <=1048576**. Reserving all 20000 allowed weight tasks gives A<=514288. A=500000 passes that conservative numerical bound; A=1000000 cannot. No remapping is introduced, so 1M is not eligible even if memory were sufficient.

TA sequence number is uint16_t on wire (`ub-header.h:949`, request serialization/deserialization and ACK). Each Jetty carries only one WQE. Fixed scaled activation128B/segment1024 yields one request TA, and a weight chunk4096B yields four; default whole expert49152B yields48. These cannot wrap. An admission audit must reject a per-transfer ceil(bytes/segment)>65536 if extending parameters; no test here changes segment/chunk sizes. Application tracker offsets/coverage IDs are uint64_t; task/assignment/token fields are uint32_t and CSV event task is signed int. The conservative <=1048576 task bound also prevents signed int task narrowing in tested cases.

TPN/PSN/MSN masks are24 bits (`ub-header.cc:1164-1189`). EP64 TPN formula a*64+b+1 stays<=4096. Requested successful-range scaled task/TA counts stay below24-bit total request packet sequence counts even in a conservative all-to-one-TP bound (without an unbounded retransmission scenario). Native protocol handles sequence state; packet and ACK correctness must still pass execution verification. No assumption of arbitrary parameter safety is made.

## Non-payload bottlenecks

Planner stores explicit token/source/top-k and physical mappings, N×E demand/N×P quotas and audit JSON, with A<=2M plus numeric preflight and128 cooperative CPU reference threads. Adapter retains input, plan, assignment and transfer objects while dumping JSON. They require separate measured host stages.

Native `UbJettyManager::ResolveWqeLifecycleLocalId` (`ub-function.cc:697-718`) checks candidate lifecycle IDs by scanning all registered Jetty records on that manager. `SubmitWqe`/registration calls this path; even globally unique task IDs require a full negative scan. Repeated submissions can therefore incur O(sum over ranks of J_rank²) host work under the retained-per-task-Jetty design. This is a source-derived potential cost driver, not a measured attribution of a specific fraction of wall time; no native lookup optimization is performed.

Relay dependency construction scans weight tasks quadratically. Executor creates and retains per-remote-task Jetty/WQE objects; native packet/TA events and full traces grow separately. Event count uses ns3 `Simulator::GetEventCount()`, read only after `Run()` returns; missing on a killed process is reported as unavailable. Application CSV row count is a different metric.

The unchanged strict verifier reads all events/JSON/raw payloads; it scans all A assignments for every token O(T*A), and `time('token_complete',id=token)` scans the T token-complete events for every token O(T²). Relay task scans are O(W_tasks²), with payload slice copies and full-W temporary verification buffers. Verifier timeout is independent of simulator success. No indexing, streaming or algorithm optimization is introduced in this capacity study.

## Scope of changes

Initial 50K/100K runs keep original caps. The only initial executor change is an optional post-run JSON counter output, proven byte-identical on all generated small NoBalance/ChunkStreaming artifacts. Larger opt-in caps are considered only after both lower scales fully verify. If a resource guard stops a lower scale, no cap increase is needed or justified by this experiment. Runtime guards protect process-tree RSS, whole-cgroup memory, wall time and disk; payload estimates alone are insufficient.
