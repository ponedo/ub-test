#!/usr/bin/env python3
"""Synthetic evidence/mutation tests; these never build or run the simulator.

The fixture is only an input generator, not independent evidence of a simulation.
Hard-coded graph, hash and header tests anchor the checker separately; mutations
prove that malformed persisted evidence cannot pass the postflight checks.
"""
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from collections import Counter, defaultdict

import verify as v


def write_csv(root, name, rows, fields=None):
    rows = list(rows)
    fields = fields or list(rows[0])
    with (root / name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def alter_csv(root, name, change):
    data = v.rows(root, name)
    fields = list(data[0])
    change(data)
    write_csv(root, name, data, fields)


def fixture(root, strategy="multicast", fanout=4, mode="compact-oracle", length=12288, debug=False):
    """Construct consistent synthetic, compact evidence, never fake run output."""
    if strategy != "multicast":
        mode = "full"
    graph, candidate, gain, relay, cut = v.expected_graph(strategy, fanout, length)
    graph_rows = [dict(edge, dependencies=";".join(map(str, edge["dependencies"]))) for edge in graph]
    write_csv(root, "executed-transfers.csv", graph_rows)
    payload = bytes((20261016 + i * 17 + (i // 256) * 29) % 256 for i in range(length))
    source_sha = hashlib.sha256(payload).hexdigest()
    timeline = []
    events, identities, audits = [], [], []
    for edge in graph:
        task, count = edge["task"], edge["bytes"]
        ntas = (count + 1023) // 1024
        sent = max([100] + [timeline[parent]["ready_ps"] for parent in edge["dependencies"]])
        ready = sent + 10 + (ntas - 1) * 4 + 3
        timeline.append(dict(task=task, send_ps=sent, ready_ps=ready, sender_complete_ps=ready + 5,
                             last_ta_complete_ps=ready, ta_count=ntas, completed_tas=ntas, covered_bytes=count,
                             payload_sha256=hashlib.sha256(payload[edge["offset"]:edge["offset"] + count]).hexdigest()))
        if debug:
            def event(name, time, node, offset=0, size=count):
                return dict(time_ps=time, event=name, stage=2, id=edge["id"], node=node, offset=offset, bytes=size, task=task)
            events.append(event("send", sent, edge["source"]))
            for offset in range(0, count, 1024):
                size = min(1024, count - offset)
                at = sent + 10 + (offset // 1024) * 4
                jetty = 4097 + task if strategy == "multicast" else edge["source"] * 64 + edge["target"] + 1
                identities.append(dict(time_ps=at, task=task, jetty=jetty, logical_ssn=0, offset=offset, bytes=size))
                audits.append(dict(task=task, offset=offset, bytes=size, admitted_ps=at,
                                   received_ps=at + 1, verified_ps=at + 2, completed_ps=at + 3))
                for i, name in enumerate(("ta_admitted", "target_received", "payload_verified", "target_complete")):
                    events.append(event(name, at + i, edge["source"] if i == 0 else edge["target"], offset, size))
            events += [event("edge_ready", ready, edge["target"]), event("sender_complete", ready + 5, edge["source"])]
    write_csv(root, "task-timeline.csv", timeline)
    targets = []
    for rank in range(1, fanout + 1):
        tasks = [timeline[edge["task"]] for edge in graph if edge["target"] == rank]
        ready = max(task["ready_ps"] for task in tasks)
        targets.append(dict(expert=0, physical=127 + rank, rank=rank, payload_bytes=length,
                            ready_ps=ready, ready_duration_ps=ready - 100,
                            sender_complete_ps=max(task["sender_complete_ps"] for task in tasks),
                            received_sha256=source_sha, received_fnv1a64="unused-by-verifier"))
    write_csv(root, "targets.csv", targets)
    write_csv(root, "receiver-stats.csv", [dict(rank=rank, is_target=int(1 <= rank <= fanout),
              received_payload_bytes=length if 1 <= rank <= fanout else 0,
              received_tas=sum((edge["bytes"] + 1023) // 1024 for edge in graph if edge["target"] == rank),
              ready_physical_count=int(1 <= rank <= fanout)) for rank in range(64)])
    expected_packets = v.packet_expectations(graph, strategy, mode, fanout, length)
    hist, classes = Counter(), defaultdict(lambda: [0, 0])
    for (node, port, kind, size), count in expected_packets.items():
        hist[node, port, "tx", size] += count
        peer_node, peer_port = v.peer((node, port))
        hist[peer_node, peer_port, "rx", size] += count
        classes[node, port, kind][0] += count
        classes[node, port, kind][1] += count * size
    write_csv(root, "packet-sizes.csv", [dict(node=n, port=p, direction=d, control=0, wire_bytes=size,
              packets=count, cells_per_packet=(size + 159) // 160) for (n, p, d, size), count in sorted(hist.items())])
    write_csv(root, "packet-counts.csv", [dict(node=n, port=p, kind=kind, packets=value[0], wire_bytes=value[1])
              for (n, p, kind), value in sorted(classes.items())])
    ports, queues = [], []
    for node, port in sorted(v.PORTS):
        tx_bytes = sum(size * count for (n, p, d, size), count in hist.items() if (n, p, d) == (node, port, "tx"))
        rx_bytes = sum(size * count for (n, p, d, size), count in hist.items() if (n, p, d) == (node, port, "rx"))
        tx_cells = sum(((size + 159) // 160) * count for (n, p, d, size), count in hist.items() if (n, p, d) == (node, port, "tx"))
        rx_cells = sum(((size + 159) // 160) * count for (n, p, d, size), count in hist.items() if (n, p, d) == (node, port, "rx"))
        tx_count = sum(count for (n, p, d, size), count in hist.items() if (n, p, d) == (node, port, "tx"))
        peak = max([0] + [size for (n, p, d, size) in hist if (n, p, d) == (node, port, "tx")])
        ports.append(dict(node=node, port=port, wire_tx_bytes=tx_bytes, wire_rx_bytes=rx_bytes,
                          egress_peak=peak, ingress_peak=peak, initial_cells=6553,
                          consumed_cells=tx_cells, returned_cells=rx_cells, restored_cells=tx_cells,
                          free_cells=6553, pending_cells=0, blocked_queries=0,
                          observed_consumed_cells=tx_cells, observed_returned_cells=rx_cells,
                          egress_capacity=524288, ingress_capacity=1048576, egress_final_bytes=0, switch_buffer_final_bytes=0))
        queues.append(dict(node=node, port=port, peak_egress_bytes=peak, wire_tx_bytes=tx_bytes,
                           dequeued_packets=tx_count, total_egress_residence_ps=tx_count))
    write_csv(root, "ports.csv", ports)
    write_csv(root, "queue-stats.csv", queues)
    native = {}
    for edge in graph:
        jetty = 4097 + edge["task"] if strategy == "multicast" else edge["source"] * 64 + edge["target"] + 1
        key = edge["source"], edge["target"], jetty
        native[key] = dict(source=edge["source"], target=edge["target"], jetty=jetty,
                           ta_una=1, ta_nxt=1, active_wqes=0, tx_una=1, tx_nxt=1,
                           tx_outstanding=0, rx_una=1, rx_nxt=1, rx_outstanding=0)
    write_csv(root, "native-final-state.csv", native.values())
    shared = strategy == "multicast"
    ntas = (length + 1023) // 1024
    header = v.charged_header(mode, fanout) if shared else 78
    group_complete = max(t["sender_complete_ps"] for t in timeline) if shared else 0
    envelope_count = ntas if shared and fanout > 1 else 0
    header_fields = "group,fanout,header_model,payload_sent,wire_data_bytes,charged_header_bytes,native_child_header_bytes,full_model_header_bytes,envelopes,oracle_pending_count,oracle_native_metadata_bytes,peak_oracle_native_metadata_bytes,peak_oracle_envelopes,window_wait_queries,empty_wait_queries,barrier_queries".split(",")
    oracle = shared and fanout > 1 and mode != "full"
    headers = [dict(zip(header_fields, [1, fanout, mode, length, length + header * ntas, header * ntas,
                78 * fanout * ntas, v.charged_header("full", fanout) * ntas, envelope_count,
                0, 0, 129 * fanout if oracle else 0, 1 if oracle else 0, 0, 0, 0]))] if shared else []
    write_csv(root, "header-accounting.csv", headers, header_fields)
    write_csv(root, "replication-state.csv", [dict(node=64, admitted=ntas if shared else 0,
              released=ntas if shared else 0, branches=ntas * fanout if shared else 0,
              branch_dequeues=ntas * fanout if shared else 0, parent_bytes=0, branch_bytes=0,
              descriptors=0, outstanding_parents=0)])
    if shared:
        write_csv(root, "multicast-groups.csv", [dict(group=1, expert=0, source=0, task=i, target=i + 1,
                  physical=128 + i, bytes=length, receiver_ready_ps=targets[i]["ready_ps"],
                  sender_complete_ps=targets[i]["sender_complete_ps"], group_complete_ps=group_complete) for i in range(fanout)])
        write_csv(root, "multicast-stats.csv", [dict(group=1, source=0, fanout=fanout, payload_bytes=length,
                  wire_bytes=length + header * ntas, envelopes=envelope_count, window_wait_checks=0, empty_wait_checks=0)])
    main = sum(edge["bytes"] for edge in graph if edge["source"] == 0)
    forwarded = sum(edge["bytes"] for edge in graph if edge["source"] != 0)
    source_wire = sum(size * count for (node, port, kind, size), count in expected_packets.items()
                      if node == 0 and kind in ("weight_write", "multicast_data"))
    all_ready = max(t["ready_ps"] for t in targets)
    summary = dict(schema=1, status="PASS", workload="single-expert-weight-fanout-only", planner_executed=False,
                   tokens=0, compute_events=0, strategy=strategy, header_model=mode, ep=64, expert=0, source=0,
                   fanout=fanout, weight_bytes=length, ta_bytes=1024, chunk_bytes=4096, shard_cut=cut,
                   seed=20261016, link_gbps=100, link_delay_ns=20, source_sha256=source_sha,
                   relay_candidate_count=candidate, relay_gain=gain, relay_enabled=relay,
                   relay_direct_fallback=strategy == "chunk-streaming" and not relay,
                   weight_wqes=len(graph), weight_tas=sum(t["ta_count"] for t in timeline), sender_completions=len(graph),
                   logical_receiver_bytes=fanout * length, main_logical_send_bytes=main, relay_logical_send_bytes=forwarded,
                   source_wire_payload_bytes=length if shared else main, source_data_wire_bytes=source_wire,
                   source_full_native_child_equivalent_data_wire_bytes=fanout * (length + 78 * ntas),
                   weights_start_ps=100, all_receivers_ready_ps=all_ready, all_receivers_ready_duration_ps=all_ready - 100,
                   all_senders_complete_ps=max(t["sender_complete_ps"] for t in targets), multicast_group_complete_ps=group_complete,
                   multicast_envelopes=envelope_count, multicast_window_wait_queries=0,
                   multicast_empty_wait_queries=0, multicast_barrier_queries=0,
                   executed_graph_fnv1a64=v.fnv1a64((root / "executed-transfers.csv").read_bytes()))
    (root / "fanout-summary.json").write_text(json.dumps(summary))
    if debug:
        identities.sort(key=lambda row: (row["time_ps"], row["task"], row["offset"]))
        ssns = Counter()
        for row in identities:
            source = graph[row["task"]]["source"]
            key = source, row["jetty"]
            row["logical_ssn"] = ssns[key]
            ssns[key] += 1
        write_csv(root, "ta-identity.csv", identities)
        write_csv(root, "ta-audit.csv", audits)
        write_csv(root, "events.csv", sorted(events, key=lambda row: row["time_ps"]))
        wire = []
        for (node, port, direction, size), count in sorted(hist.items()):
            for _ in range(count):
                wire.append(dict(time_ps=len(wire), event=direction, node=node, port=port,
                                 wire_bytes=size, cells=(size + 159) // 160, kind="native_data"))
        write_csv(root, "wire.csv", wire)
    return summary


class IndependentAnchors(unittest.TestCase):
    def test_header_constants_and_singleton(self):
        for mode in ("full", "compact-oracle", "ideal-oracle"):
            self.assertEqual(v.charged_header(mode, 1), 78)
        self.assertEqual(v.charged_header("full", 8), 1128)
        self.assertEqual(v.charged_header("compact-oracle", 8), 160)
        self.assertEqual(v.charged_header("ideal-oracle", 8), 32)

    def test_f4_graph_exact_order_and_group_dependencies(self):
        graph, _, _, relay, cut = v.expected_graph("chunk-streaming", 4, 12288)
        self.assertTrue(relay)
        self.assertEqual(cut, 8192)
        self.assertEqual([(e["source"], e["target"], e["offset"], e["bytes"], e["dependencies"]) for e in graph],
                         [(0, 1, 0, 4096, []), (0, 2, 0, 4096, []),
                          (0, 1, 4096, 4096, []), (0, 2, 4096, 4096, []),
                          (0, 1, 8192, 4096, []), (0, 2, 8192, 4096, []),
                          (1, 3, 0, 4096, [0, 1]), (1, 3, 4096, 4096, [2, 3]),
                          (1, 3, 8192, 4096, [4, 5]), (2, 4, 0, 4096, [0, 1]),
                          (2, 4, 4096, 4096, [2, 3]), (2, 4, 8192, 4096, [4, 5])])

    def test_f8_leaf_ownership_and_fallback(self):
        graph, _, _, _, _ = v.expected_graph("chunk-streaming", 8, 12288)
        ownership = {(e["source"], e["target"]) for e in graph if e["source"]}
        self.assertEqual(ownership, {(1, 3), (1, 5), (1, 7), (2, 4), (2, 6), (2, 8)})
        for fanout in (1, 2, 3):
            graph, _, _, relay, _ = v.expected_graph("chunk-streaming", fanout, 12288)
            self.assertFalse(relay)
            self.assertEqual(len(graph), fanout)
            self.assertTrue(all(e["source"] == 0 and e["bytes"] == 12288 for e in graph))

    def test_payload_period_and_partial_slice(self):
        raw = bytes((20261016 + i * 17 + (i // 256) * 29) % 256 for i in range(140000))
        for offset, length in ((0, 12288), (65535, 70000), (101, 5), (131000, 1000)):
            self.assertEqual(v.payload_sha256(offset, length), hashlib.sha256(raw[offset:offset + length]).hexdigest())


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def reject(self, filename, mutation, match):
        fixture(self.root)
        alter_csv(self.root, filename, mutation)
        with self.assertRaisesRegex(v.VerificationError, match):
            v.verify(self.root)

    def test_all_small_matrix_models(self):
        for fanout in (1, 2, 3, 4, 8):
            for strategy, mode in (("direct", "full"), ("chunk-streaming", "full"), ("multicast", "full"),
                                   ("multicast", "compact-oracle"), ("multicast", "ideal-oracle")):
                with self.subTest(fanout=fanout, strategy=strategy, mode=mode):
                    fixture(self.root, strategy, fanout, mode)
                    result = v.verify(self.root)
                    self.assertEqual(result["status"], "PASS")
                    self.assertFalse(result["evidence_scope"]["per_ta_event_replay"])

    def test_partial_ta_and_shard_boundaries(self):
        fixture(self.root, "chunk-streaming", 4, length=12345)
        self.assertEqual(v.verify(self.root)["status"], "PASS")

    def test_debug_independent_ta_replay(self):
        fixture(self.root, fanout=1, debug=True)
        self.assertTrue(v.verify(self.root)["evidence_scope"]["per_ta_event_replay"])

    def test_wrong_digest(self):
        self.reject("targets.csv", lambda data: data[0].update(received_sha256="0" * 64), "SHA256")

    def test_missing_target(self):
        self.reject("targets.csv", lambda data: data.pop(), "membership")

    def test_non_target_receiver(self):
        self.reject("receiver-stats.csv", lambda data: data[-1].update(received_payload_bytes="1024"), "receiver payload")

    def test_duplicate_target(self):
        self.reject("targets.csv", lambda data: data.append(dict(data[0])), "duplicate")

    def test_early_ready(self):
        self.reject("task-timeline.csv", lambda data: data[0].update(ready_ps="100"), "premature")

    def test_early_sender(self):
        self.reject("task-timeline.csv", lambda data: data[0].update(sender_complete_ps="100"), "premature")

    def test_missing_ta(self):
        self.reject("task-timeline.csv", lambda data: data[0].update(completed_tas="11"), "TA count/coverage")

    def test_wrong_ta_payload(self):
        self.reject("task-timeline.csv", lambda data: data[0].update(payload_sha256="f" * 64), "SHA256")

    def test_wrong_graph(self):
        self.reject("executed-transfers.csv", lambda data: data[0].update(source="2"), "graph task")

    def test_missing_all_relay_dependencies(self):
        fixture(self.root, "chunk-streaming", 4)
        alter_csv(self.root, "executed-transfers.csv", lambda data: data[6].update(dependencies="0"))
        with self.assertRaisesRegex(v.VerificationError, "dependencies"):
            v.verify(self.root)

    def test_relay_sent_before_second_parent(self):
        fixture(self.root, "chunk-streaming", 4)
        alter_csv(self.root, "task-timeline.csv", lambda data: data[6].update(send_ps="100"))
        with self.assertRaisesRegex(v.VerificationError, "dependency/start gate"):
            v.verify(self.root)

    def test_native_response_omission(self):
        self.reject("packet-counts.csv", lambda data: data.__setitem__(slice(None), [r for r in data if r["kind"] != "transaction_response"]), "missing native")

    def test_native_ack_omission(self):
        self.reject("packet-counts.csv", lambda data: data.__setitem__(slice(None), [r for r in data if r["kind"] != "transport_ack"]), "missing native")

    def test_wrong_wire_header_size(self):
        self.reject("packet-sizes.csv", lambda data: data[0].update(wire_bytes=str(int(data[0]["wire_bytes"]) + 160)), "CBFC cells")

    def test_charge_uses_ceil_not_floor(self):
        self.reject("packet-sizes.csv", lambda data: data[0].update(cells_per_packet="0"), "ceil")

    def test_missing_port(self):
        self.reject("ports.csv", lambda data: data.pop(), "128 physical ports")

    def test_credit_leak(self):
        self.reject("ports.csv", lambda data: data[0].update(restored_cells=str(int(data[0]["restored_cells"]) - 1)), "local credit")

    def test_legal_subthreshold_pending_return(self):
        fixture(self.root)
        def pending(data):
            source = next(row for row in data if row["node"] == "0")
            switch = next(row for row in data if row["node"] == "64" and row["port"] == "0")
            source["restored_cells"] = str(int(source["restored_cells"]) - 1)
            source["free_cells"] = "6552"
            switch["pending_cells"] = "1"
        alter_csv(self.root, "ports.csv", pending)
        self.assertEqual(v.verify(self.root)["status"], "PASS")

    def test_link_rx_mismatch(self):
        self.reject("packet-sizes.csv", lambda data: data[0].update(packets=str(int(data[0]["packets"]) + 1)), "conservation|budget")

    def test_queue_overflow(self):
        self.reject("ports.csv", lambda data: data[0].update(egress_peak="524289"), "capacity exceeded")

    def test_queue_not_drained(self):
        self.reject("ports.csv", lambda data: data[0].update(egress_final_bytes="1"), "not drained")

    def test_native_window_not_drained(self):
        self.reject("native-final-state.csv", lambda data: data[0].update(tx_nxt="2"), "window not drained")

    def test_oracle_context_leak(self):
        self.reject("header-accounting.csv", lambda data: data[0].update(oracle_pending_count="1"), "oracle context not drained")

    def test_oracle_unbounded_context(self):
        self.reject("header-accounting.csv", lambda data: data[0].update(peak_oracle_envelopes="1001"), "bounded")

    def test_logical_header_conflated_with_charged(self):
        self.reject("header-accounting.csv", lambda data: data[0].update(charged_header_bytes=data[0]["native_child_header_bytes"]), "header byte accounting")

    def test_replication_branch_missing(self):
        self.reject("replication-state.csv", lambda data: data[0].update(branch_dequeues="1"), "branch conservation")

    def test_replication_leak(self):
        self.reject("replication-state.csv", lambda data: data[0].update(descriptors="1"), "replication not drained")

    def test_debug_duplicate_ta(self):
        fixture(self.root, fanout=1, debug=True)
        alter_csv(self.root, "ta-identity.csv", lambda data: data.append(dict(data[0])))
        with self.assertRaisesRegex(v.VerificationError, "SSN|duplicate"):
            v.verify(self.root)

    def test_debug_event_omission(self):
        fixture(self.root, fanout=1, debug=True)
        alter_csv(self.root, "events.csv", lambda data: data.__setitem__(slice(None), [r for r in data if not (r["event"] == "payload_verified" and r["offset"] == "0")]))
        with self.assertRaisesRegex(v.VerificationError, "out-of-order"):
            v.verify(self.root)

    def test_debug_wire_omission(self):
        fixture(self.root, fanout=1, debug=True)
        alter_csv(self.root, "wire.csv", lambda data: data.pop())
        with self.assertRaisesRegex(v.VerificationError, "histogram reconciliation"):
            v.verify(self.root)

    def test_online_pass_cannot_replace_evidence(self):
        fixture(self.root)
        (self.root / "validation.json").write_text('{"status":"PASS"}')
        (self.root / "packet-sizes.csv").unlink()
        with self.assertRaisesRegex(v.VerificationError, "missing evidence"):
            v.verify(self.root)


if __name__ == "__main__":
    unittest.main()
