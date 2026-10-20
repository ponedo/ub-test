# Task and semantic batch ledger

User authorized 2026-10-20: audit and bounded A–E native retransmission validation on original dot host, fixed v2 project commit 3587954cccecaaf59e9578c5645c745bf78583e5. Publish separate branch then stop. No new reliability protocol, envelope-format change, Planner/Chunk/MoE or multi-switch work.

## Startup
Original host filesystem retained accepted native b8375b51 but v2 temporary directories were absent after recovery. Restored all 39 v2 deliverables from GitHub exact commit. New disposable retrans-native worktree: 108 baseline SHA256 entries and eight v2 changed-source hashes match. Launcher present; tools submodule/parser absent; use accepted self-contained C++ fixtures, not claim Quick Start is ready. Never modify historical working trees. Assertions enabled; existing guard unchanged (3600s stage,6GiB RSS,7GiB AS,min8GiB disk,min2GiB tmp,min1.5GiB memory). Sequential builds/tests only.

## Pre-edit audit checkpoint
Native GBN and selective DATA descriptor retention and replay exist (transport.cc:809–837; retrans.cc:30–92,1201–1225). Default EnableRetrans=false. Retry exhaustion is assertion, not orderly WQE failure. V2 inherits an explicit retransmission installation prohibition and only coalesces aligned first sends. Full detailed audit follows in AUDIT.md. No new ACK/timer/controller necessary.

## Batch Reuse Map
Pre-refactor: fixed v2 project and native sources above.
Semantic batch 1: adapter separates native retry/control and original sends; test-only sink fault seam.
Old active symbols: lightweight::SharedSource::Install/Control/IsEmpty/IsLimited; writev2::SharedSource::GetNextPacket; UbTransportChannel::GetNextPacket/IsLimited/HasPendingGbnRetransmissionForTest; UbSwitch::SinkTpDataPacket.
Reuse: inherit unchanged v2 encoder/association and native GBN builder, normal allocator/egress/CBFC. Extract no retransmission algorithm. Separate new adapter with copied validated installation boundary without retransmission prohibition, plus native retained-work eligibility. Retained-state visibility keeps wrapper summary live until native timeout triggers normal port scheduling; no independent polling/timer.
Test seam: default-null multiplicity callback at native sink after actual physical reception/credit return/endpoint validation, before TP consumes packet. 0 drops,1 normal,2 repeats TP delivery. Drops therefore occur after switch envelope split and actual downstream link, at endpoint transport ingress. This is not physical-link corruption or CBFC credit loss. Repeated delivery does not consume a fictitious second link credit. Faults never synthesize success, ACK, or timer.
Preserve ordering: native control first, then native GBN retry individually, then all-ready new-send coalescing. Native PSN/WQE/header/payload/ACK/RTO algorithms unchanged. Only GBN in this bounded experiment, selective not claimed.
Focused validation: normal baseline, last B PSN11 drop, duplicate PSN11, final B TPACK/TAACK loss, persistent B PSN11 drop with bounded stop and native exhausted-assert separate run; disabled-retrans negative. Source/physical packet/state/queue traces, payload/execution count, no premature group completion. Old v1/v2 and unicast regressions.
Reapproval triggers: native ACK/RTO/state/completion algorithm changes, unrelated public API/lifecycle owner changes, unexplained repeated failures. Stop/report rather than redesign.

## Review before runs
Read-only review confirmed native priority and callback no-fault preservation. Corrected trace parser to identify common DL config before parsing data header; removed inactive inherited feedback/header counters from summary. External verifier requires actual fault activation, exact request replay identity/payload, every physical queue/link hop, reverse response replay, bounded native descriptor/timer state, and credit conservation. Packet UID alone is not a unique replay identifier (native payload fragments can preserve UID); verifier also matches TP/PSN and replay-time interval. No protocol semantic changes.

## Actual bounded evidence checkpoint
Native build PASS,2339.13s,857684KiB peak RSS,no guard stop. First fixture compile failed on an unqualified inherited enum name; qualified lightweight::HeaderMode and rebuilt successfully. Eight fault/control runs produced expected verified outcomes. data-once exactly1 source WRITE replay; response-once1 reverse TAACK replay; duplicate no reexecution. Persistent bounded retains1 expected unconfirmed descriptor/timer; native exhaustion aborts at21.54696us,not a graceful failure. ACK-only loss has WQE success before later transport quiescence. All old v1/v2 cases passed; historical regression chain subsequently completed successfully. Reviewer checked actual traces and clarified pending-credit and post-link injection limitations.
