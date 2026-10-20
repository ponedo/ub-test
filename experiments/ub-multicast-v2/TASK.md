# Batch reuse and closeout

# Batch reuse map and execution ledger

Pre-refactor project commit: 1b35acbdc83226b90f39aeb5aad935425dec3a04. Initial audit reconstruction: 42067a3 (108 hashes match). Final original dot host accepted baseline: b8375b51a094d3b1217b697989e1ab979f609e64 (same 108 hashes).

Semantic batch: WRITE v2 codec + inherited SharedSource eligibility + switch parent/branch ownership with distinct sizes. User task authorizes this local ownership refactor and new mode. Old paths: native GetNextPacket, SharedSource IsLimited/Control, ResolveURMAOutput, CompleteNetworkProcessing, QueueManager branch association, allocator OnIngressReleased. Reuse mode: extend existing parent accounting with default equal-size behavior; subclass source queue; use native parsers/routing and old multitarget fixture. Preserve native window/PSN/SSN, transaction completion, all ordinary unicast and v1 branches. Explicit delta: switch emits native unicast bytes and source envelope omits tags and per-child DL. Exclude retransmission/CC/new ACK algorithms/Planner/multi-switch/large UltraEP. Validation: codec positives/negative inputs; 12KiB and 64KiB v1/v2; existing three-target, competition, small-queue/window fixtures; native/old multicast/Direct/Chunk tests where dependencies permit. Reapproval only for scope outside the user-authorized design or guard relaxation (never planned).

Initial validation: clean project worktree, remote reference matches, reconstructed native source SHA256 108/108. Startup: ns3 exists; tools submodule and build artifacts absent. No simulation claimed ready yet. No local skills in ub-test; native AGENTS.md and implementation workflow read. Existing resource guard reused unchanged. Default host build concurrency at most -j2, sequential tests.


## Original dot host closeout

Parent imported checksum-verified existing implementation into isolated native/project trees; all eight native files match the transferred patch, preserving accepted historical trees. Sequential bounded validation was rerun on original dot host. See run-ledger.md and results for exact outcomes. Only additional implementation was verification-gate hardening; no protocol semantic expansion. Read-only review completed. Private raw payload, trace, host inventory and private evidence indexes are excluded from GitHub.
