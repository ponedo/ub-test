#!/usr/bin/env python3
"""Independent, fail-closed postflight for the weights-only fanout fixture.

This module does not import the simulator, the production graph generator, or an
online validator. Expected graph, payload digests, packets and CBFC cell charges
are reconstructed here. Summary runs retain per-WQE observations, not per-TA
event history: those runs cannot independently replay individual TA event order.
Debug fixtures additionally replay the persisted per-TA events and identities.
No claimed PASS in validation.json is used as evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

EP = 64
SEED = 20261016
TA = 1024
CHUNK = 4096
MAX_BYTES = 18 * 1024 * 1024
PORTS = {(n, 0) for n in range(EP)} | {(EP, n) for n in range(EP)}
KINDS = {"weight_write", "multicast_data", "transaction_response", "transport_ack", "credit"}


class VerificationError(ValueError):
    """Evidence is absent, inconsistent, or violates an experiment invariant."""


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def integer(value, label="integer", minimum=0):
    require(not isinstance(value, bool), f"{label}: boolean is not an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"{label}: invalid integer {value!r}") from exc
    require(str(result) == str(value), f"{label}: noncanonical integer {value!r}")
    require(result >= minimum, f"{label}: negative value")
    return result


def rows(root, name):
    path = Path(root) / name
    require(path.is_file(), f"missing evidence: {name}")
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames),
                f"{name}: absent/duplicate columns")
        result = list(reader)
    require(all(None not in row and all(v is not None for v in row.values()) for row in result),
            f"{name}: malformed CSV")
    return result


def numeric(row, *keys):
    return tuple(integer(row[k], k) for k in keys)


def indexed(items, keys, label):
    result = {}
    for row in items:
        key = numeric(row, *keys)
        require(key not in result, f"{label}: duplicate {key}")
        result[key] = row
    return result


def peer(port):
    node, index = port
    return (EP, node) if node < EP else (index, 0)


@lru_cache(maxsize=1)
def payload_period():
    # The seed formula has period 65536. Do not use the emitted source digest
    # as the expected digest, or a matching corruption could escape detection.
    return bytes((SEED + i * 17 + (i >> 8) * 29) & 255 for i in range(65536))


@lru_cache(maxsize=128)
def _payload_sha256(offset_mod, length):
    period = payload_period()
    digest = hashlib.sha256()
    if offset_mod:
        first = min(length, len(period) - offset_mod)
        digest.update(period[offset_mod:offset_mod + first])
        length -= first
    while length >= len(period):
        digest.update(period)
        length -= len(period)
    digest.update(period[:length])
    return digest.hexdigest()


def payload_sha256(offset, length):
    return _payload_sha256(offset % 65536, length)


def fnv1a64(data):
    value = 14695981039346656037
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return f"{value:016x}"


def expected_graph(strategy, fanout, length):
    """Independent port of the documented selection rule, with ordered edges."""
    candidates = min(math.isqrt(fanout), 8, fanout - 1) if fanout > 1 else 0
    gain = fanout - max(candidates, (fanout - candidates + candidates - 1) // candidates) if candidates else 0
    relay = strategy == "chunk-streaming" and fanout >= 4 and candidates > 0 and gain >= 2
    cut = length // 3 * 2 if length % 3 == 0 else 0
    graph = []

    def edge(src, dst, offset, count, deps=()):
        physical = 127 + dst
        graph.append(dict(task=len(graph), stage=2, id=physical, source=src,
                          target=dst, physical=physical, bytes=count,
                          source_physical=0 if src == 0 else 127 + src,
                          offset=offset, dependencies=list(deps)))

    if not relay:
        for target in range(1, fanout + 1):
            edge(0, target, 0, length)
    else:
        # Single expert and zero prior load: rank/ordinal tie-breaking selects
        # the first ranks. Leaf assignment uses projected load and child count.
        relays = list(range(1, candidates + 1))
        owners = {rank: [] for rank in relays}
        projected = {rank: 0 for rank in relays}
        for i, target in enumerate(range(candidates + 1, fanout + 1)):
            owner = relays[i] if i < candidates else min(
                relays, key=lambda r: (projected[r], len(owners[r]), r, r - 1))
            owners[owner].append(target)
            projected[owner] += length
        bounds = [0] + ([cut] if cut else []) + [length]
        ranges = [(offset, min(CHUNK, end - offset))
                  for begin, end in zip(bounds, bounds[1:])
                  for offset in range(begin, end, CHUNK)]
        parents = {}
        for offset, count in ranges:
            parents[offset, count] = list(range(len(graph), len(graph) + candidates))
            for relay_rank in relays:
                edge(0, relay_rank, offset, count)
        for relay_rank in relays:
            for offset, count in ranges:
                for target in owners[relay_rank]:
                    edge(relay_rank, target, offset, count, parents[offset, count])
    return graph, candidates, gain, relay, cut


def charged_header(mode, fanout):
    if fanout == 1:
        return 78
    return 32 + {"full": 137, "compact-oracle": 16, "ideal-oracle": 0}[mode] * fanout


def packet_expectations(graph, strategy, mode, fanout, length):
    """Return exact non-CBFC TX histogram and class counts for every hop."""
    packets = Counter()  # node, port, kind, actual serialized size
    shared = strategy == "multicast" and fanout > 1
    for edge in graph:
        src, dst, count = edge["source"], edge["target"], edge["bytes"]
        for offset in range(0, count, TA):
            payload = min(TA, count - offset)
            if not shared:
                for node, port in ((src, 0), (EP, dst)):
                    packets[node, port, "weight_write", payload + 78] += 1
            # Native feedback is retained in every header model. A TA response
            # and its ACK use the native path, as does the request ACK.
            for node, port in ((dst, 0), (EP, src)):
                packets[node, port, "transaction_response", 62] += 1
            for node, port in ((src, 0), (dst, 0), (EP, src), (EP, dst)):
                packets[node, port, "transport_ack", 62] += 1
    if shared:
        header = charged_header(mode, fanout)
        for offset in range(0, length, TA):
            size = min(TA, length - offset) + header
            for node, port in [(0, 0)] + [(EP, rank) for rank in range(1, fanout + 1)]:
                packets[node, port, "multicast_data", size] += 1
    return packets


def verify_graph(root, summary, graph):
    actual = rows(root, "executed-transfers.csv")
    require(len(actual) == len(graph), "graph WQE count")
    for expected, row in zip(graph, actual):
        for key, value in expected.items():
            observed = [integer(x, "dependency") for x in row[key].split(";") if x] if key == "dependencies" else integer(row[key], key)
            require(observed == value, f"graph task {expected['task']} {key}: expected {value}, got {observed}")
    data = (Path(root) / "executed-transfers.csv").read_bytes()
    require(summary["executed_graph_fnv1a64"] == fnv1a64(data), "graph content hash")
    return hashlib.sha256(data).hexdigest()


def verify_targets(root, summary, graph):
    length, fanout = summary["weight_bytes"], summary["fanout"]
    digest = payload_sha256(0, length)
    require(summary["source_sha256"] == digest, "source deterministic SHA256")
    targets = indexed(rows(root, "targets.csv"), ("rank",), "targets")
    require(set(targets) == {(r,) for r in range(1, fanout + 1)}, "target membership/extra receiver")
    timeline = indexed(rows(root, "task-timeline.csv"), ("task",), "task timeline")
    require(set(timeline) == {(i,) for i in range(len(graph))}, "task timeline membership")
    start = integer(summary["weights_start_ps"], "weights_start_ps")
    target_bytes, target_tas = Counter(), Counter()
    target_ready, target_sender = defaultdict(int), defaultdict(int)
    for edge in graph:
        task, count, target = edge["task"], edge["bytes"], edge["target"]
        row = timeline[task,]
        sent, ready, sender, last = numeric(row, "send_ps", "ready_ps", "sender_complete_ps", "last_ta_complete_ps")
        ntas = (count + TA - 1) // TA
        require(numeric(row, "ta_count", "completed_tas", "covered_bytes") == (ntas, ntas, count), f"task {task}: TA count/coverage")
        require(start <= sent <= last <= ready <= sender, f"task {task}: premature readiness/sender")
        require(ready == last, f"task {task}: readiness not latest child TA")
        expected_send = max([start] + [integer(timeline[parent,]["ready_ps"]) for parent in edge["dependencies"]])
        require(sent == expected_send, f"task {task}: relay dependency/start gate")
        require(row["payload_sha256"] == payload_sha256(edge["offset"], count), f"task {task}: received payload SHA256")
        target_bytes[target] += count
        target_tas[target] += ntas
        target_ready[target] = max(target_ready[target], ready)
        target_sender[target] = max(target_sender[target], sender)
    hashes = []
    for rank in range(1, fanout + 1):
        row = targets[rank,]
        require(numeric(row, "expert", "physical", "payload_bytes") == (0, 127 + rank, length), "target expert/physical/bytes")
        require(target_bytes[rank] == length, "target exact graph coverage")
        require(numeric(row, "ready_ps", "sender_complete_ps") == (target_ready[rank], target_sender[rank]), "target aggregate completion")
        require(integer(row["ready_duration_ps"]) == target_ready[rank] - start, "target duration")
        require(row["received_sha256"] == digest, f"rank {rank}: received SHA256")
        hashes.append(dict(rank=rank, bytes=length, sha256=digest))
    receivers = indexed(rows(root, "receiver-stats.csv"), ("rank",), "receiver stats")
    require(set(receivers) == {(r,) for r in range(EP)}, "receiver stats must include all 64 ranks")
    for rank in range(EP):
        row = receivers[rank,]
        require(numeric(row, "received_payload_bytes", "received_tas") == (target_bytes[rank], target_tas[rank]), "unexpected/missing receiver payload")
        require(numeric(row, "is_target", "ready_physical_count") == ((1, 1) if 1 <= rank <= fanout else (0, 0)), "receiver membership/readiness count")
    all_ready, all_sender = max(target_ready.values()), max(target_sender.values())
    require(summary["all_receivers_ready_ps"] == all_ready and summary["all_senders_complete_ps"] == all_sender, "global readiness/sender aggregation")
    require(summary["all_receivers_ready_duration_ps"] == all_ready - start, "global readiness duration")
    return hashes, timeline


def verify_network(root, summary, expected):
    ports = indexed(rows(root, "ports.csv"), ("node", "port"), "ports")
    require(set(ports) == PORTS, "all 128 physical ports required")
    hist = Counter()
    for row in rows(root, "packet-sizes.csv"):
        node, port, control, size, count, cells = numeric(row, "node", "port", "control", "wire_bytes", "packets", "cells_per_packet")
        direction = row["direction"]
        require((node, port) in PORTS and direction in {"tx", "rx"} and control in (0, 1), "packet histogram port/direction/control")
        require(count > 0 and size > 0, "empty packet histogram bucket")
        require(cells == (0 if control else (size + 159) // 160), "CBFC cells must charge ceil(actual GetSize/160)")
        require(not control or size == 40, "native credit frame size")
        key = node, port, direction, control, size
        require(key not in hist, "duplicate packet-size bucket")
        hist[key] = count
    expected_hist = Counter()
    expected_classes = Counter()
    expected_bytes = Counter()
    for (node, port, kind, size), count in expected.items():
        expected_hist[node, port, "tx", 0, size] += count
        expected_classes[node, port, kind] += count
        expected_bytes[node, port, kind] += count * size
    actual_data_hist = Counter({key: value for key, value in hist.items() if key[2] == "tx" and not key[3]})
    require(actual_data_hist == expected_hist, "actual charged non-credit packet-size/count budget (including native feedback)")
    classes = {}
    for row in rows(root, "packet-counts.csv"):
        node, port, count, size = numeric(row, "node", "port", "packets", "wire_bytes")
        kind = row["kind"]
        key = node, port, kind
        require((node, port) in PORTS and kind in KINDS and key not in classes and count > 0, "packet class membership/duplicate")
        classes[key] = (count, size)
        if kind == "credit":
            require((count, size) == (hist[node, port, "tx", 1, 40], count * 40), "credit packet class count/bytes")
        else:
            require((count, size) == (expected_classes[key], expected_bytes[key]), f"native/data packet class budget: {key}")
    require({key for key in classes if key[2] != "credit"} == set(expected_classes), "missing native ACK/response/data packet class")
    for node, port in PORTS:
        if hist[node, port, "tx", 1, 40]:
            require((node, port, "credit") in classes, "omitted credit class")
    for (node, port, direction, control, size), count in hist.items():
        other = peer((node, port))
        require(hist[*other, "rx" if direction == "tx" else "tx", control, size] == count, "all-link packet histogram conservation")
    totals = defaultdict(lambda: [0, 0, 0])
    for (node, port, direction, control, size), count in hist.items():
        values = totals[node, port, direction]
        values[0] += size * count
        values[1] += count
        values[2] += 0 if control else ((size + 159) // 160) * count
    for key, row in ports.items():
        other = ports[peer(key)]
        tx, rx = totals[*key, "tx"], totals[*key, "rx"]
        require(numeric(row, "wire_tx_bytes", "wire_rx_bytes") == (tx[0], rx[0]), "port actual wire totals")
        require(numeric(row, "consumed_cells", "observed_consumed_cells") == (tx[2], tx[2]), "port consumed actual cells")
        require(numeric(row, "returned_cells", "observed_returned_cells") == (rx[2], rx[2]), "port returned actual cells")
        initial, consumed, restored, free, pending = numeric(row, "initial_cells", "consumed_cells", "restored_cells", "free_cells", "pending_cells")
        require(initial == 6553, "unchanged initial native CBFC credit")
        require(initial - consumed + restored == free and free <= initial, "local credit conservation")
        require(consumed == integer(other["returned_cells"]), "cross-link consumed/returned conservation")
        require(consumed == restored + integer(other["pending_cells"]), "cross-link restored/pending conservation")
        # Native returns below the threshold can remain pending; they are not
        # packet/queue leaks, and must not be silently rounded away.
        require(pending <= integer(row["returned_cells"]), "pending credits exceed returns")
        peak, capacity = numeric(row, "egress_peak", "egress_capacity")
        ingress, ingress_capacity = numeric(row, "ingress_peak", "ingress_capacity")
        require(capacity == 524288 and ingress_capacity == 1048576, "unchanged queue capacities")
        require(peak <= capacity and ingress <= ingress_capacity, "queue capacity exceeded")
        require(numeric(row, "egress_final_bytes", "switch_buffer_final_bytes") == (0, 0), "queue/buffer not drained")
    queues = indexed(rows(root, "queue-stats.csv"), ("node", "port"), "queue stats")
    require(set(queues) == PORTS, "queue evidence must cover all ports")
    for key, row in queues.items():
        require(numeric(row, "peak_egress_bytes", "wire_tx_bytes", "dequeued_packets") ==
                (integer(ports[key]["egress_peak"]), totals[*key, "tx"][0], totals[*key, "tx"][1]), "queue/packet dequeue reconciliation")
        integer(row["total_egress_residence_ps"], "queue residence")
    return ports, classes, hist


def verify_native(root, graph, strategy):
    expected = {}
    for edge in graph:
        jetty = EP * EP + 1 + edge["task"] if strategy == "multicast" else edge["source"] * EP + edge["target"] + 1
        key = edge["source"], edge["target"], jetty
        expected[key] = expected.get(key, 0) + (edge["bytes"] + TA - 1) // TA
    native = indexed(rows(root, "native-final-state.csv"), ("source", "target", "jetty"), "native state")
    require(set(native) == set(expected), "native Pair Jetty/multicast child identity/count")
    for key, row in native.items():
        require(numeric(row, "active_wqes", "tx_outstanding", "rx_outstanding") == (0, 0, 0), "native outstanding state")
        for prefix in ("ta", "tx", "rx"):
            require(integer(row[prefix + "_una"]) == integer(row[prefix + "_nxt"]), "native window not drained")
    return len(native)


def verify_debug(root, graph, timeline, strategy, histogram):
    """Replay exact persisted TA transitions only when Debug evidence exists."""
    root = Path(root)
    have_events, have_ids = (root / "events.csv").exists(), (root / "ta-identity.csv").exists()
    if not have_ids:
        return {"mode": "per-WQE-summary", "per_ta_event_replay": False,
                "boundary": "Individual TA order/exact-once is checked online; only per-WQE counts, bytes, latest TA completion and received-buffer hashes are persisted."}
    require(have_events, "Debug TA identities require events")
    identity = {}
    next_ssn = Counter()
    for row in rows(root, "ta-identity.csv"):
        task, jetty, ssn, offset, count, time = numeric(row, "task", "jetty", "logical_ssn", "offset", "bytes", "time_ps")
        require(task < len(graph), "debug unknown TA task")
        edge = graph[task]
        expected_jetty = (EP * EP + 1 + task if strategy == "multicast" else edge["source"] * EP + edge["target"] + 1)
        require(jetty == expected_jetty, "debug Jetty identity")
        pair = edge["source"], jetty
        require(ssn == next_ssn[pair], "debug logical SSN progression")
        next_ssn[pair] += 1
        require(offset < edge["bytes"] and offset % TA == 0 and count == min(TA, edge["bytes"] - offset), "debug TA range")
        require((task, offset) not in identity, "debug duplicate TA identity")
        identity[task, offset] = (count, time)
    expected_keys = {(edge["task"], offset) for edge in graph for offset in range(0, edge["bytes"], TA)}
    require(set(identity) == expected_keys, "debug exact TA coverage")
    sequence = {"ta_admitted": 0, "target_received": 1, "payload_verified": 2, "target_complete": 3}
    observed = defaultdict(list)
    sends, ready, senders = {}, {}, {}
    last_time = 0
    for row in rows(root, "events.csv"):
        time = integer(row["time_ps"])
        require(time >= last_time, "debug event clock reversed")
        last_time = time
        event = row["event"]
        require(event not in {"compute_start", "compute_end", "expert_start", "expert_end", "token_complete"}, "debug non-weight work")
        task = integer(row["task"], "task", minimum=-1)
        if task < 0:
            continue
        require(task < len(graph), "debug unknown task")
        edge = graph[task]
        require(integer(row["stage"]) == 2 and integer(row["id"]) == edge["id"], "debug task metadata")
        node, offset, count = numeric(row, "node", "offset", "bytes")
        if event in sequence:
            key = task, offset
            require(key in identity and count == identity[key][0], "debug segment identity")
            require(len(observed[key]) == sequence[event], "debug duplicate/missing/out-of-order TA event")
            require(node == (edge["source"] if event == "ta_admitted" else edge["target"]), "debug segment receiver")
            require(time >= integer(timeline[task,]["send_ps"]), "debug TA before send")
            if event == "ta_admitted":
                require(time == identity[key][1], "debug TA identity time")
            observed[key].append(time)
        elif event in ("send", "edge_ready", "sender_complete"):
            dest = sends if event == "send" else ready if event == "edge_ready" else senders
            require(task not in dest, "debug duplicate WQE event")
            require(node == (edge["target"] if event == "edge_ready" else edge["source"]), "debug WQE event endpoint")
            dest[task] = time
    require(set(observed) == expected_keys and all(len(v) == 4 for v in observed.values()), "debug incomplete TA lifecycle")
    audit = indexed(rows(root, "ta-audit.csv"), ("task", "offset"), "debug TA audit")
    require(set(audit) == expected_keys, "debug TA audit membership")
    for key, row in audit.items():
        require(integer(row["bytes"]) == identity[key][0], "debug TA audit length")
        require(numeric(row, "admitted_ps", "received_ps", "verified_ps", "completed_ps") == tuple(observed[key]), "debug TA audit/event mismatch")
    for edge in graph:
        task = edge["task"]
        row = timeline[task,]
        require((sends.get(task), ready.get(task), senders.get(task)) == numeric(row, "send_ps", "ready_ps", "sender_complete_ps"), "debug/summary task timing")
        require(max(observed[task, offset][-1] for offset in range(0, edge["bytes"], TA)) == integer(row["last_ta_complete_ps"]), "debug latest TA completion")
    wire = Counter()
    last_time = 0
    for row in rows(root, "wire.csv"):
        time, node, port, size, cells = numeric(row, "time_ps", "node", "port", "wire_bytes", "cells")
        require(time >= last_time, "debug wire clock reversed")
        last_time = time
        require(row["event"] in {"tx", "rx"} and (node, port) in PORTS, "debug wire endpoint/direction")
        require(row["kind"] in {"credit", "multicast_data", "native_data"}, "debug wire classification")
        control = int(row["kind"] == "credit")
        require(cells == (0 if control else (size + 159) // 160), "debug actual packet cell charge")
        wire[node, port, row["event"], control, size] += 1
    require(wire == histogram, "debug wire/size histogram reconciliation")
    return {"mode": "Debug-per-TA", "per_ta_event_replay": True,
            "packet_event_histogram_replay": True, "checked_TAs": len(identity)}


def verify(root):
    root = Path(root)
    try:
        summary = json.loads((root / "fanout-summary.json").read_text())
        require(summary["schema"] == 1 and summary["status"] == "PASS", "incomplete summary")
        require(summary["workload"] == "single-expert-weight-fanout-only", "wrong workload")
        require(summary["planner_executed"] is False and summary["tokens"] == 0 and summary["compute_events"] == 0, "not weights-only")
        for key, value in {"ep": EP, "expert": 0, "source": 0, "seed": SEED, "ta_bytes": TA,
                           "chunk_bytes": CHUNK, "link_gbps": 100, "link_delay_ns": 20}.items():
            require(summary[key] == value, f"fixed control changed: {key}")
        fanout, length = integer(summary["fanout"]), integer(summary["weight_bytes"])
        require(fanout in {1, 2, 3, 4, 8} and 0 < length <= MAX_BYTES, "fanout/byte range")
        strategy, mode = summary["strategy"], summary["header_model"]
        require(strategy in {"direct", "chunk-streaming", "multicast"} and mode in {"full", "compact-oracle", "ideal-oracle"}, "strategy/header model")
        require(strategy == "multicast" or mode == "full", "oracle applied to non-multicast")
        graph, candidate, gain, relay, cut = expected_graph(strategy, fanout, length)
        require((summary["relay_candidate_count"], summary["relay_gain"], summary["relay_enabled"], summary["shard_cut"]) == (candidate, gain, relay, cut), "relay rule/config")
        require(summary["relay_direct_fallback"] == (strategy == "chunk-streaming" and not relay), "relay fallback")
        tas = sum((edge["bytes"] + TA - 1) // TA for edge in graph)
        require((summary["weight_wqes"], summary["weight_tas"], summary["sender_completions"]) == (len(graph), tas, len(graph)), "logical WQE/TA/completion counts")
        main = sum(edge["bytes"] for edge in graph if not edge["source"])
        forwarded = sum(edge["bytes"] for edge in graph if edge["source"])
        require((summary["logical_receiver_bytes"], summary["main_logical_send_bytes"], summary["relay_logical_send_bytes"]) == (fanout * length, main, forwarded), "source/relay logical payload distinction")
        source_payload = length if strategy == "multicast" else main
        require(summary["source_wire_payload_bytes"] == source_payload, "source payload injection")
        graph_sha = verify_graph(root, summary, graph)
        hashes, timeline = verify_targets(root, summary, graph)
        packets = packet_expectations(graph, strategy, mode, fanout, length)
        ports, classes, histogram = verify_network(root, summary, packets)
        source_wire = sum(size * count for (node, port, kind, size), count in packets.items()
                          if node == 0 and kind in {"weight_write", "multicast_data"})
        require(summary["source_data_wire_bytes"] == source_wire, "source actual data wire formula")
        require(summary["source_full_native_child_equivalent_data_wire_bytes"] == fanout * (length + 78 * ((length + TA - 1) // TA)), "native child equivalent bytes")
        native_count = verify_native(root, graph, strategy)
        replay = verify_debug(root, graph, timeline, strategy, histogram)
        # The additional treatment/replication records are verified below. They
        # are separate from the online validator's assertions.
        treatment = verify_treatment(root, summary, packets)
        return dict(status="PASS", schema=1, workload=summary["workload"], strategy=strategy,
                    header_model=mode, fanout=fanout, weight_bytes=length,
                    checked_WQEs=len(graph), checked_TAs=tas, checked_ports=len(ports),
                    checked_native_endpoints=native_count, evidence_scope=replay,
                    source_payload_bytes=source_payload, relay_payload_bytes=forwarded,
                    source_data_wire_bytes=source_wire, source_all_wire_bytes=integer(ports[0, 0]["wire_tx_bytes"]),
                    completion_ps=summary["all_receivers_ready_duration_ps"],
                    executed_graph_sha256=graph_sha, targets=hashes, header_accounting=treatment,
                    checks=["independent_relay_graph_and_dependencies", "all_rank_receiver_coverage", "deterministic_received_sha256",
                            "per_WQE_TA_coverage_and_ready_sender_gates", "actual_packet_size_and_feedback_budgets",
                            "all_link_packet_and_credit_conservation", "queue_capacity_and_drain", "native_window_drain"])
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"missing/malformed independent evidence: {exc}") from exc


def verify_treatment(root, summary, packets):
    """Header accounting schema is intentionally separate from online PASS."""
    # Filled by the benchmark-specific evidence writer; missing fields fail
    # closed, including terminal replication state and Oracle context cost.
    rows_ = rows(root, "header-accounting.csv")
    length, fanout = summary["weight_bytes"], summary["fanout"]
    ntas = (length + TA - 1) // TA
    shared = summary["strategy"] == "multicast"
    header = charged_header(summary["header_model"], fanout) if shared else 78
    oracle = shared and fanout > 1 and summary["header_model"] != "full"
    require(len(rows_) == (1 if shared else 0), "header accounting cardinality")
    replication_rows = rows(root, "replication-state.csv")
    require(len(replication_rows) == 1, "replication state cardinality")
    replication = replication_rows[0]
    parents = ntas if shared else 0
    branches = parents * fanout
    require(numeric(replication, "node", "admitted", "released", "branches", "branch_dequeues") ==
            (EP, parents, parents, branches, branches), "physical multicast parent/branch conservation")
    require(numeric(replication, "parent_bytes", "branch_bytes", "descriptors", "outstanding_parents") == (0, 0, 0, 0), "replication not drained")
    envelopes = ntas if shared and fanout > 1 else 0
    require(summary["multicast_envelopes"] == envelopes, "multicast envelope count/singleton bypass")
    if shared:
        row = rows_[0]
        require(numeric(row, "group", "fanout", "payload_sent", "wire_data_bytes", "charged_header_bytes", "native_child_header_bytes", "full_model_header_bytes", "envelopes") ==
                (1, fanout, length, length + header * ntas, header * ntas, 78 * fanout * ntas,
                 charged_header("full", fanout) * ntas, envelopes), "charged/reference/native header byte accounting")
        require(row["header_model"] == summary["header_model"], "header model identity")
        require(numeric(row, "oracle_pending_count", "oracle_native_metadata_bytes") == (0, 0), "oracle context not drained")
        peak_bytes, peak_envelopes = numeric(row, "peak_oracle_native_metadata_bytes", "peak_oracle_envelopes")
        if oracle:
            require(0 < peak_envelopes <= min(1000, ntas), "oracle context not bounded by native send window")
            require(peak_bytes == 129 * fanout * peak_envelopes, "oracle retained metadata accounting")
        else:
            require((peak_bytes, peak_envelopes) == (0, 0), "full/singleton retained oracle context")
        for field, summary_key in (("window_wait_queries", "multicast_window_wait_queries"),
                                   ("empty_wait_queries", "multicast_empty_wait_queries"),
                                   ("barrier_queries", "multicast_barrier_queries")):
            require(integer(row[field]) == summary[summary_key], "multicast query counters")
        require(integer(row["barrier_queries"]) == integer(row["window_wait_queries"]) + integer(row["empty_wait_queries"]), "multicast barrier query accounting")
        groups = indexed(rows(root, "multicast-groups.csv"), ("task",), "multicast groups")
        require(set(groups) == {(task,) for task in range(fanout)}, "multicast child membership")
        targets = indexed(rows(root, "targets.csv"), ("rank",), "targets")
        for task in range(fanout):
            member = groups[task,]
            target = targets[task + 1,]
            require(numeric(member, "group", "expert", "source", "target", "physical", "bytes") == (1, 0, 0, task + 1, 128 + task, length), "multicast native child identity")
            require(numeric(member, "receiver_ready_ps", "sender_complete_ps", "group_complete_ps") ==
                    (integer(target["ready_ps"]), integer(target["sender_complete_ps"]), summary["multicast_group_complete_ps"]), "multicast child completion")
        require(summary["multicast_group_complete_ps"] >= summary["all_senders_complete_ps"], "group completed before native children")
        stats = rows(root, "multicast-stats.csv")
        require(len(stats) == 1 and numeric(stats[0], "group", "source", "fanout", "payload_bytes", "wire_bytes", "envelopes") ==
                (1, 0, fanout, length, length + header * ntas, envelopes), "multicast actual source statistics")
    else:
        require(summary["multicast_group_complete_ps"] == 0, "non-multicast completion")
    source_packets = sum(count for (node, port, kind, size), count in packets.items()
                         if node == 0 and kind in {"weight_write", "multicast_data"})
    actual_headers = header * source_packets
    logical_native_headers = 78 * fanout * ntas
    return {"charged_header_per_source_data_packet": header,
            "charged_source_header_bytes": actual_headers,
            "logical_native_child_prefix_bytes": logical_native_headers,
            "charged_minus_logical_native_prefix_bytes": actual_headers - logical_native_headers,
            "source_header_bytes_saved_versus_full": (charged_header("full", fanout) - header) * ntas if shared else 0,
            "oracle": oracle,
            "oracle_control_plane_cost_modeled_bytes": 0 if oracle else None,
            "note": "Oracle restores omitted native prefixes/tags from zero-cost simulator context. Retained metadata is not the same quantity as wire-byte savings. Actual GetSize controls serialization and CBFC."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(args.directory)
    except VerificationError as exc:
        result = {"status": "FAIL", "error": str(exc)}
        if args.out:
            args.out.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
        return 1
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
