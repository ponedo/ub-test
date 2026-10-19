#!/usr/bin/env python3
"""Bounded native-window/CBFC and feedback gates for all three header models.

Only the isolated header-pressure.cc is built. The accepted native library and
the original multitarget fixture are never edited. All child commands use the
existing guard, one at a time. Full packet/event/payload evidence stays private.
"""
import argparse
import csv
import difflib
import hashlib
import json
import sys
from pathlib import Path

if not __debug__:
    raise RuntimeError("Correctness checks require assertions enabled")

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
ORIGINAL = EXPERIMENTS / "ub-lightweight-multicast-adapter/multitarget.cc"
ORIGINAL_SHA256 = "a6cfc0e607b93f092254353ce2154fa92e568ac4fd161ff9af0a25969d4d4b77"
FIXTURE = HERE / "header-pressure.cc"
sys.path.insert(0, str(EXPERIMENTS / "wqe-completion-fix"))
from guard import run

MODES = ["full", "compact-oracle", "ideal-oracle"]
CASES = [
    ("three-target", "basic", 16384, 1000, False, ""),
    ("dynamic", "dynamic", 8192, 1000, False, ""),
    ("window2", "basic", 32768, 2, False, ""),
    ("pressure", "competition", 16384, 1000, True, ""),
    ("missing-feedback", "basic", 4096, 1000, False, "missing"),
    ("duplicate-feedback", "basic", 4096, 1000, False, "duplicate"),
    ("wrong-feedback", "basic", 4096, 1000, False, "wrong"),
]
FAILURES = {
    "missing": "unfinished group: missing feedback",
    "duplicate": "duplicate feedback detected",
    "wrong": "feedback kind/member",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def header_bytes(mode, fanout):
    if fanout == 1:
        return 78
    return 32 + {"full": 137, "compact-oracle": 16, "ideal-oracle": 0}[mode] * fanout


def verify(case, mode, name, scenario, size, window, pressure):
    """Independent extension of the original received-byte/event verifier."""
    events = read_csv(case / "events.csv")
    wire = read_csv(case / "wire.csv")
    ports = read_csv(case / "ports.csv")
    windows = read_csv(case / "windows.csv")
    summary = json.loads((case / "summary.json").read_text())
    expected = {1001: [1, 2] if scenario == "dynamic" else [1, 2, 3]}
    if scenario == "dynamic":
        expected[1002] = [2, 3]

    def event(kind, task, rank=None):
        return [row for row in events if row["event"] == kind and
                int(row["task"]) == task and
                (rank is None or int(row["rank"]) == rank)]

    hashes = []
    source_wire = 0
    source_packets = 0
    for task, members in expected.items():
        submit = event("group_submit", task)
        finish = event("group_complete", task)
        assert len(submit) == len(finish) == 1
        final_sender = 0
        for rank in members:
            ta = event("target_complete", task, rank)
            assert sorted((int(row["offset"]), int(row["bytes"])) for row in ta) == [
                (offset, min(1024, size - offset)) for offset in range(0, size, 1024)]
            chunks = event("chunk_ready", task, rank)
            assert sorted((int(row["offset"]), int(row["bytes"])) for row in chunks) == [
                (offset, min(4096, size - offset)) for offset in range(0, size, 4096)]
            for chunk in chunks:
                start = int(chunk["offset"])
                end = start + int(chunk["bytes"])
                assert int(chunk["time_ps"]) == max(
                    int(row["time_ps"]) for row in ta if start <= int(row["offset"]) < end)
            ready = event("receiver_ready", task, rank)
            sender = event("sender_complete", task, rank)
            feedback = event("feedback_received", task, rank)
            received = event("envelope_received", task, rank)
            assert len(ready) == len(sender) == 1 and len(feedback) == len(ta)
            assert [int(row["offset"]) for row in received] == list(range(size // 1024))
            assert all(int(row["bytes"]) == 1024 for row in received)
            assert int(ready[0]["time_ps"]) == max(int(row["time_ps"]) for row in ta)
            assert int(sender[0]["time_ps"]) >= int(ready[0]["time_ps"])
            assert int(sender[0]["time_ps"]) >= max(int(row["time_ps"]) for row in feedback)
            assert len({row["offset"] for row in feedback}) == len(feedback)
            final_sender = max(final_sender, int(sender[0]["time_ps"]))
            actual = (case / f"payload-{task}-{rank}.bin").read_bytes()
            wanted = bytes((task * 73 + i * 131 + (i >> 8) * 17) % 251 for i in range(size))
            assert actual == wanted
            hashes.append({"task": task, "rank": rank, "bytes": len(actual),
                           "sha256": hashlib.sha256(actual).hexdigest()})
        assert int(finish[0]["time_ps"]) == final_sender
        for rank in set(range(1, 5)) - set(members):
            assert not event("target_complete", task, rank)
            assert not (case / f"payload-{task}-{rank}.bin").exists()
        source = [row for row in wire if row["event"] == "tx" and
                  int(row["node"]) == 0 and row["packet_class"] == "multicast_data" and
                  int(row["task"]) == task]
        assert len(source) == size // 1024
        assert all(int(row["bytes"]) == 1024 + header_bytes(mode, len(members)) for row in source)
        source_packets += len(source)
        source_wire += sum(int(row["bytes"]) for row in source)
        for rank in members:
            branch = [row for row in wire if row["event"] == "rx" and
                      int(row["node"]) == rank and row["packet_class"] == "multicast_data" and
                      int(row["task"]) == task]
            assert len(branch) == len(source)
            assert [row["bytes"] for row in branch] == [row["bytes"] for row in source]

    if scenario == "dynamic":
        assert int(event("group_submit", 1002)[0]["time_ps"]) >= int(
            event("group_complete", 1001)[0]["time_ps"])

    # Verify every packet's actual serialized size and propagation on every link.
    for rank in range(5):
        for sender, sport, receiver, rport in [(rank, 0, 5, rank), (5, rank, rank, 0)]:
            tx = [row for row in wire if row["event"] == "tx" and
                  int(row["node"]) == sender and int(row["port"]) == sport]
            rx = [row for row in wire if row["event"] == "rx" and
                  int(row["node"]) == receiver and int(row["port"]) == rport]
            assert len(tx) == len(rx)
            for sent, received in zip(tx, rx):
                assert all(sent[key] == received[key] for key in
                           ["bytes", "packet_class", "task", "tp_opcode", "ta_opcode"])
                assert int(received["time_ps"]) - int(sent["time_ps"]) == int(sent["bytes"]) * 80 + 20000

    port_map = {(int(row["node"]), int(row["port"])): row for row in ports}
    assert len(port_map) == 10
    for (node, port), row in port_map.items():
        tx = [packet for packet in wire if packet["event"] == "tx" and
              int(packet["node"]) == node and int(packet["port"]) == port and
              packet["packet_class"] != "credit"]
        rx = [packet for packet in wire if packet["event"] == "rx" and
              int(packet["node"]) == node and int(packet["port"]) == port and
              packet["packet_class"] != "credit"]
        assert int(row["consumed"]) == sum((int(packet["bytes"]) + 159) // 160 for packet in tx)
        assert int(row["returned"]) == sum((int(packet["bytes"]) + 159) // 160 for packet in rx)
        assert (10 if pressure else 6553) - int(row["consumed"]) + int(row["restored"]) == int(row["free"])
        assert 0 <= int(row["peak"]) <= (1600 if pressure else 524288)
        peer = port_map[(port, 0) if node == 5 else (5, node)]
        assert int(row["consumed"]) == int(peer["returned"])
        assert int(peer["returned"]) == int(row["restored"]) + int(peer["pending"])

    assert summary["status"] == "PASS" and summary["header_model"] == mode
    assert summary["groups"] == len(expected)
    assert summary["source_payload_bytes"] == size * len(expected)
    assert summary["source_data_wire_bytes"] == source_wire
    assert summary["envelopes"] == source_packets
    assert summary["branches"] == sum(len(members) * size // 1024 for members in expected.values())
    assert summary["feedback"] == summary["branches"]
    assert summary["oracle_pending_envelopes"] == summary["oracle_native_metadata_bytes"] == 0
    assert all(0 <= int(row["tp_nxt"]) - int(row["tp_una"]) <= window for row in windows)
    assert all(0 <= int(row["ta_nxt"]) - int(row["ta_una"]) <= 512 for row in windows)
    assert all(int(row["tp_outstanding"]) <= 1000 for row in windows)
    final = [row for row in windows if row["event"] == "final_drain"]
    assert len(final) == 3 and all(row["tp_nxt"] == row["tp_una"] and
                                 row["ta_nxt"] == row["ta_una"] and
                                 int(row["tp_outstanding"]) == 0 for row in final)
    maximum_tp_inflight = max(int(row["tp_nxt"]) - int(row["tp_una"]) for row in windows)
    if name == "window2":
        assert maximum_tp_inflight == 2 and summary["window_waits"] > 0
    if pressure:
        assert summary["blocked_queries"] == sum(int(row["blocked"]) for row in ports) > 0
        assert len(event("background_complete", 9001)) == 1
        assert sum(int(row["bytes"]) for row in event("background_target", 9001)) == 4 * size
    if mode == "full":
        assert summary["oracle_peak_envelopes"] == summary["oracle_peak_native_metadata_bytes"] == 0
    else:
        assert 0 < summary["oracle_peak_envelopes"] <= summary["oracle_envelope_limit"] == window
        assert 0 < summary["oracle_peak_native_metadata_bytes"] <= 129 * max(map(len, expected.values())) * window
    assert not any(row["event"] == "fault_injected" for row in events)
    result = {
        "status": "PASS", "header_model": mode, "source_data_wire_bytes": source_wire,
        "maximum_tp_inflight": maximum_tp_inflight, "payloads": hashes,
        "checks": ["actual_payload_bytes_and_sha256", "exact_TA_and_chunk_coverage",
                   "receiver_sender_group_causality", "native_feedback_count",
                   "exact_member_set", "actual_header_bytes", "physical_link_serialization",
                   "actual_wire_credit_cells", "cross_link_credit_conservation",
                   "queue_limits", "native_window_bounds_and_drain", "oracle_bound_and_drain"],
    }
    dump(case / "independent-validation.json", result)
    return summary, result


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--native", type=Path, help="Build this isolated fixture against the pinned native tree")
    source.add_argument("--binary", type=Path, help="Use an already-built header-pressure fixture")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    assert sha256(ORIGINAL) == ORIGINAL_SHA256, "original fixture source changed"
    assert f"Original source SHA256: {ORIGINAL_SHA256}" in FIXTURE.read_text()
    patch = "".join(difflib.unified_diff(
        ORIGINAL.read_text().splitlines(keepends=True), FIXTURE.read_text().splitlines(keepends=True),
        fromfile="ub-lightweight-multicast-adapter/multitarget.cc",
        tofile="ub-multicast-fanout-header/header-pressure.cc"))
    (out / "fixture-source-diff.patch").write_text(patch)
    provenance = {
        "original_source": "experiments/ub-lightweight-multicast-adapter/multitarget.cc",
        "original_sha256": ORIGINAL_SHA256, "fixture_sha256": sha256(FIXTURE),
        "source_diff_sha256": hashlib.sha256(patch.encode()).hexdigest(),
        "adapter_sha256": sha256(EXPERIMENTS / "ub-lightweight-multicast-adapter/adapter.h"),
        "runner_sha256": sha256(Path(__file__).resolve()),
        "guard_sha256": sha256(EXPERIMENTS / "wqe-completion-fix/guard.py"),
        "modes": MODES, "planned_case_count": len(MODES) * len(CASES),
        "target_execution_delay_changed": False,
    }
    dump(out / "source-provenance.json", provenance)
    if args.native:
        native = args.native.resolve()
        pinned = json.loads((HERE / "native-source-sha256.json").read_text())
        for relative, digest in pinned.items():
            assert sha256(native / relative) == digest, relative
        binary = out / "header-pressure"
        command = ["c++", "-std=c++20", "-O3", "-g", FIXTURE,
                   "-I" + str(native / "build/include"), "-L" + str(native / "build/lib"),
                   "-Wl,--disable-new-dtags", "-Wl,-rpath," + str(native / "build/lib"),
                   "-lns3.44-unified-bus", "-lns3.44-internet", "-lns3.44-network", "-lns3.44-core",
                   "-o", binary]
        built = run(command, out / "build", 3600, case=out)
        assert built["status"] == "PASS", "isolated fixture build failed"
        provenance["native_source_hashes"] = pinned
    else:
        binary = args.binary.resolve()
    provenance["binary_sha256"] = sha256(binary)
    dump(out / "source-provenance.json", provenance)
    ledger = []
    for mode in MODES:
        for name, scenario, size, window, pressure, fault in CASES:
            case_name = mode + "-" + name
            case = out / "cases" / case_name
            host = out / "hosts" / case_name
            command = [binary, "--out=" + str(case), "--headerModel=" + mode,
                       "--scenario=" + scenario, "--bytes=" + str(size),
                       "--window=" + str(window), "--pressure=" + str(int(pressure))]
            if fault:
                command.append("--fault=" + fault)
            result = run(command, host, 3600, case=out)
            row = {"case": case_name, "header_model": mode, "scenario": scenario,
                   "bytes": size, "window": window, "pressure": pressure, "fault": fault,
                   "status": result["status"], "host": {key: result[key] for key in
                       ["wall_seconds", "user_cpu_seconds", "system_cpu_seconds",
                        "peak_rss_kib", "returncode", "guard", "limits"]}}
            ledger.append(row)
            try:
                if fault:
                    console = (host / "console.txt").read_text()
                    assert result["returncode"] < 0 and not result["guard"]
                    assert FAILURES[fault] in console
                    assert not (case / "summary.json").exists()
                    events = read_csv(case / "events.csv")
                    assert sum(event["event"] == "fault_injected" for event in events) == 1
                    assert not any(event["event"] == "group_complete" for event in events)
                    row.update(status="EXPECTED_REJECTION", expected_failure=FAILURES[fault])
                else:
                    assert result["status"] == "PASS", "fixture did not complete"
                    row["summary"], row["validation"] = verify(
                        case, mode, name, scenario, size, window, pressure)
            except Exception as error:
                row.update(status="FAIL", verification_error=str(error), error_type=type(error).__name__)
                dump(out / "results.json", ledger)
                raise
            dump(out / "results.json", ledger)
    assert len(ledger) == 21
    print("HEADER PRESSURE/WINDOW/FEEDBACK PASS", len(ledger))


if __name__ == "__main__":
    main()
