"""Read completed passive diagnostics; never launches or changes a simulation.

All generated files are PRIVATE review artifacts. Publication requires a separate
review; neither a raw ring nor the full transfer graph is copied to the output.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

KINDS = dict(enumerate([
    "voq_push", "voq_pop", "allocation_select", "grant_start", "grant_commit",
    "egress_enqueue", "egress_send", "port_busy_start", "port_busy_end",
    "tx_start", "rx", "tp_enqueue", "tp_pop", "tp_head", "tp_limited",
    "tp_ack_before", "tp_ack_after", "tp_response_before", "tp_response_after",
    "envelope_decode", "native_branch", "queue_bind", "tp_empty",
]))
KINDS.update({100: "submit", 101: "native_send", 102: "target_receive",
              103: "receiver_ready", 104: "sender_complete", 105: "weight_ready",
              106: "allready_observation_transition", 107: "representative_grant"})
KINDS.update({23: "grant_rejected", 24: "grant_no_ingress"})
METRICS = {0: "voq_residence_ps", 1: "selection_to_commit_ps",
           2: "requested_allocation_service_ps", 3: "egress_wait_ps",
           4: "pure_serialization_ps", 5: "tx_bytes", 6: "rx_bytes",
           7: "explicit_tx_delay_ps", 8: "rejected_allocation_elapsed_ps",
           9: "no_ingress_allocation_elapsed_ps", 10: "committed_allocation_elapsed_ps"}
PARTS = ["tx_busy_union_ps", "allocator_pending_excluding_tx_ps", "uncovered_idle_ps"]
MODES = ["chunk-streaming", "multicast-v2"]
NODES = {3, 5, 13, 17, 27, 36, 50, 52, 59, 64}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open(newline="") as stream:
        return [{key: int(value) if value.isdecimal() else value
                 for key, value in row.items()} for row in csv.DictReader(stream)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_identity(mapping):
    for name, expected in mapping.items():
        require(sha(name) == expected, "Frozen identity changed: " + name)


def check_parity(case, baseline):
    actual = read_json(case / "online-summary.json")
    expected = read_json(baseline / "online-summary.json")
    actual.pop("verification_wall_ns", None)
    expected.pop("verification_wall_ns", None)
    require(actual == expected, "Full accepted summary mismatch: " + str(case))
    names = ["expert-compute.csv", "expert-ready.csv", "replica-ready.csv"]
    for name in names:
        require((case / name).read_bytes() == (baseline / name).read_bytes(),
                "Exact accepted output/order mismatch: " + name)
    return {"summary_except_verification_wall_ns": True,
            "byte_identical_files": names}


def check_partition(data, end_key, allow_unmeasured=False):
    excluded = []
    for row in data:
        span = row[end_key] - row["phase_start_ps"]
        if allow_unmeasured and span > 0 and row["total_ps"] == 0 and all(row[key] == 0 for key in PARTS):
            excluded.append({**row, "exclusion_reason":
                "Port first inserted at/after phase end; no measured weight-phase span. Not counted as idle."})
            continue
        require(sum(row[key] for key in PARTS) == row["total_ps"] == span,
                "Partition does not close: " + str(row))
    return excluded


def aggregate_metrics(data):
    # Aggregate across the declared selected resources only. Durations are
    # overlapping packet-times, NEVER additive wall-time or clipped occupancy.
    grouped = {}
    for row in data:
        key = (row["metric"], row["class"], row.get("cohort", "whole_run"))
        value = grouped.setdefault(key, {"metric": key[0], "traffic_class": key[1],
            "cohort": key[2], "name": METRICS.get(key[0], "reason_or_unmatched_count"),
            "count": 0, "sum": 0, "max": 0})
        value["count"] += row["count"]
        value["sum"] += row["sum"]
        value["max"] = max(value["max"], row["max"])
    for (metric, traffic_class, cohort), value in grouped.items():
        if metric in (0, 1, 3):
            # The cohort names for matching starts/ends are the same category.
            unmatched = grouped.get((metric + 1000, traffic_class, cohort), {}).get("count", 0)
            value["unmatched_end_count"] = unmatched
            value["interval_pairing_quality"] = ("unvalidated_incomplete_matching" if unmatched
                                                 else "no_unmatched_ends_reported")
    return list(grouped.values())


def retained_voq_collisions(tail):
    pending = {}
    count = 0
    for row in tail:
        key = (row["queue_identity"], row["uid"])
        if row["kind"] == 0:
            count += key in pending
            pending[key] = row["time_ps"]
        elif row["kind"] == 1:
            pending.pop(key, None)
    return count


def packet_evidence(tail, task):
    """Select only final receiver packet, explicit parent and boundary events."""
    indexed = list(enumerate(tail))
    final_rx = [(i, row) for i, row in indexed if row["kind"] == 10
                and row["task"] == task["task"] and row["node"] == task["target"]
                and row["time_ps"] == task["last_received_ps"]]
    if not final_rx:
        return {"complete_retained_packet_chain": False,
                "missing": ["Final native target RX absent from frozen ring"]}, []
    rx_index, rx = final_rx[-1]
    branch_uid = rx["uid"]
    branch = [(i, row) for i, row in indexed if row["uid"] == branch_uid
              and row["kind"] == 20 and i <= rx_index]
    parent_uid = branch[-1][1]["parent_uid"] if branch else None
    uids = {branch_uid}
    if parent_uid is not None:
        uids.add(parent_uid)
    # ns-3 copies/fragments can preserve a UID across many wire packets. A UID
    # alone is NOT a unique transmission. Trace the last per-hop occurrence
    # backward from the final target RX and retain only those local intervals.
    fabric_tx = [(i, row) for i, row in indexed if i < rx_index and row["kind"] == 9
                 and row["uid"] == branch_uid and row["node"] not in (task["source"], task["target"])]
    fabric_rx = []
    source_tx_candidates = []
    wire_uid = parent_uid if parent_uid is not None else branch_uid
    windows = {task["target"]: (rx["time_ps"], task["receiver_ready_ps"])}
    if fabric_tx:
        tx_index, tx = fabric_tx[-1]
        fabric_rx = [(i, row) for i, row in indexed if i < tx_index and row["kind"] == 10
                     and row["uid"] == wire_uid and row["node"] == tx["node"]]
        if fabric_rx:
            fabric_rx_index, fabric_rx_event = fabric_rx[-1]
            windows[tx["node"]] = (fabric_rx_event["time_ps"], tx["time_ps"])
            source_tx_candidates = [(i, row) for i, row in indexed if i < fabric_rx_index
                and row["kind"] == 9 and row["uid"] == wire_uid and row["node"] == task["source"]]
    if source_tx_candidates:
        windows[task["source"]] = (task["last_native_send_ps"], source_tx_candidates[-1][1]["time_ps"])
    chosen = {i for i, row in indexed if row["uid"] in uids and row["kind"] <= 20
              and row["node"] in windows
              and windows[row["node"]][0] <= row["time_ps"] <= windows[row["node"]][1]}
    for i, row in indexed:
        if (row["task"] == task["task"] and row["kind"] in (12, 101, 102, 103)
                and row["time_ps"] in (task["last_native_send_ps"],
                                       task["last_received_ps"], task["receiver_ready_ps"])):
            chosen.add(i)
        if row["kind"] == 105 and row["aux0"] == task["physical"]:
            chosen.add(i)
    final_pops = [(i, tail[i]) for i in chosen if tail[i]["kind"] == 12
                  and tail[i]["node"] == task["source"]]
    if final_pops:
        pop_index, pop = max(final_pops)
        for kind in (14, 15, 16):
            candidates = [i for i, row in indexed if i < pop_index and row["kind"] == kind
                          and row["node"] == task["source"] and row["tp"] == pop["tp"]]
            if candidates:
                chosen.add(candidates[-1])
    if branch:
        group = branch[-1][1]["group"]
        for kind in (106, 107):
            candidates = [i for i, row in indexed if row["kind"] == kind
                          and row["group"] == group
                          and row["time_ps"] <= task["last_native_send_ps"]]
            if candidates:
                chosen.add(candidates[-1])
    # Attach only the latest uninterrupted retained selection associated with
    # each chosen successful commit; do not pretend earlier missing history exists.
    for i in list(chosen):
        commit = tail[i]
        if commit["kind"] != 4:
            continue
        queue = commit["queue_identity"]
        selections = []
        for j in range(i - 1, -1, -1):
            prior = tail[j]
            if prior["queue_identity"] != queue:
                continue
            if prior["kind"] == 4:
                break
            if prior["kind"] == 2:
                selections.append(j)
        if selections:
            chosen.add(min(selections))
    selected = [(i, tail[i]) for i in sorted(chosen)]
    intervals = []
    starts = {}
    for i, row in selected:
        kind = row["kind"]
        if kind in (0, 1):
            key = ("voq", row["queue_identity"], row["uid"])
        elif kind in (5, 6):
            key = ("egress", row["node"], row["port"], row["uid"])
        elif kind in (2, 4):
            key = ("allocation_selection", row["queue_identity"])
        else:
            key = None
        if kind in (0, 5, 2):
            starts.setdefault(key, row["time_ps"])
        elif kind in (1, 6, 4):
            begin = starts.pop(key, None)
            intervals.append({"type": key[0], "node": row["node"],
                "port": row["port"], "uid": row["uid"], "start_ps": begin,
                "end_ps": row["time_ps"],
                "duration_ps": None if begin is None else row["time_ps"] - begin})
        elif kind == 9:
            intervals.append({"type": "tx_service", "node": row["node"],
                "port": row["port"], "uid": row["uid"], "start_ps": row["time_ps"],
                "pure_serialization_ps": row["aux0"] - row["aux2"],
                "explicit_delay_ps": row["aux2"], "completion_busy_ps": row["aux1"]})
    missing = []
    source_tx = [row for _, row in selected if row["kind"] == 9
                 and row["node"] == task["source"]]
    if not source_tx:
        missing.append("Source TX absent")
    wire_uid = parent_uid if parent_uid is not None else branch_uid
    if not any(row["kind"] == 10 and row["uid"] == wire_uid
               and row["node"] != task["target"] for _, row in selected):
        missing.append("Intermediate fabric RX absent")
    if not any(row["kind"] == 9 and row["uid"] == branch_uid
               and row["node"] != task["source"] for _, row in selected):
        missing.append("Intermediate fabric TX absent")
    if parent_uid is not None:
        if not any(row["kind"] == 19 and row["uid"] == parent_uid for _, row in selected):
            missing.append("Parent envelope decode absent")
        if not any(row["kind"] == 9 and row["uid"] == branch_uid for _, row in selected):
            missing.append("Branch TX absent")
    transport_path_complete = not missing
    suffix = None
    if transport_path_complete and source_tx_candidates and fabric_rx and fabric_tx:
        source_event = source_tx_candidates[-1][1]
        fabric_event = fabric_tx[-1][1]
        suffix = {
            "native_dequeue_to_source_tx_ps": source_event["time_ps"] - task["last_native_send_ps"],
            "source_serialization_ps": source_event["aux0"] - source_event["aux2"],
            "source_explicit_delay_ps": source_event["aux2"],
            "source_tx_end_to_fabric_rx_ps": fabric_rx[-1][1]["time_ps"] - source_event["time_ps"] - source_event["aux0"],
            "fabric_rx_to_branch_tx_ps": fabric_event["time_ps"] - fabric_rx[-1][1]["time_ps"],
            "fabric_serialization_ps": fabric_event["aux0"] - fabric_event["aux2"],
            "fabric_explicit_delay_ps": fabric_event["aux2"],
            "fabric_tx_end_to_target_rx_ps": rx["time_ps"] - fabric_event["time_ps"] - fabric_event["aux0"],
            "target_rx_to_receiver_ready_ps": task["receiver_ready_ps"] - rx["time_ps"]}
        require(all(value >= 0 for value in suffix.values()), "Per-hop chronological selection is inconsistent")
        require(sum(suffix.values()) == task["receiver_ready_ps"] - task["last_native_send_ps"],
                "Final packet measured suffix does not close")
    resource_intervals_complete = not any(item.get("duration_ps", 0) is None for item in intervals)
    if not resource_intervals_complete:
        missing.append("One or more interval starts absent")
    # Complete here means the retained endpoint/parent path checks passed, not
    # an assertion that all earlier eligibility or queue history is available.
    return {"complete_retained_packet_chain": not missing, "missing": missing,
            "retained_transport_path_complete": transport_path_complete,
            "retained_resource_intervals_complete": resource_intervals_complete,
            "disjoint_final_packet_suffix_ps": suffix,
            "final_uid": branch_uid, "parent_uid": parent_uid,
            "identity_note": "UID may be reused across fragments; selected by final RX and latest preceding per-hop occurrence",
            "source_tx_ports": sorted({row["port"] for row in source_tx}),
            "measured_packet_intervals_not_additive": intervals}, selected


def analyze_case(case):
    for name in ("validation.json", "compute-validation.json"):
        require(read_json(case / name)["status"] == "PASS", "Validation incomplete: " + name)
    status = read_json(case / "diagnostic-status.json")
    require(status["enabled"] is True and status["incomplete"] is False,
            "Recorder disabled or incomplete")
    fifo_observer = "queue_observations_open" in status
    if fifo_observer:
        for key in ("queue_observations_open", "queue_unmatched", "queue_order_errors",
                    "queue_depth_errors", "grant_outcomes_unmatched", "grant_start_overwrites",
                    "grant_starts_open"):
            require(status.get(key) == 0, "FIFO/outcome observer integrity failure: " + key)
    summary = read_json(case / "online-summary.json")
    end = summary["timeline"]["weights_end"]
    begin = summary["event_spans"]["weights_start"][0]
    require(status["last_weight_ready_ps"] == end, "WeightReady endpoint mismatch")
    transfers = rows(case / "diagnostic-transfers.csv")
    graph_path = case / "executed-transfers.csv"
    if not graph_path.exists():
        graph_path = case / "transfers.csv"
    graph = {row["task"]: row for row in rows(graph_path)}
    critical = [row for row in transfers if row["receiver_ready_ps"] == end]
    require(critical, "No last WeightReady transfer found")
    transfer_by_id = {row["task"]: row for row in transfers}
    ports = rows(case / "diagnostic-port-partition.csv")
    prefixes = rows(case / "diagnostic-source-last-send-partition.csv")
    unmeasured_ports = check_partition(ports, "phase_end_ps", allow_unmeasured=True)
    check_partition(prefixes, "last_weight_native_send_ps")
    tail = rows(case / "diagnostic-weight-tail.csv")
    native = rows(case / "diagnostic-native-aggregates.csv")
    cohort = rows(case / "diagnostic-weight-phase-cohorts.csv")
    if fifo_observer:
        require(not any(row["metric"] in (1000, 1003) and row["count"] for row in native),
                "FIFO residence observer has unmatched ends")
        by_port = {}
        for row in native:
            if row["metric"] in (2, 8, 9, 10):
                counts = by_port.setdefault((row["node"], row["port"]), {2: 0, 8: 0, 9: 0, 10: 0})
                counts[row["metric"]] += row["count"]
        for port, counts in by_port.items():
            require(counts[2] == counts[8] + counts[9] + counts[10],
                    "Whole-run allocation outcomes do not reconcile: " + str(port))
    chosen = {}
    for task in critical:
        dependencies = str(graph[task["task"]]["dependencies"])
        task["dependencies"] = [int(value) for value in dependencies.split(";") if value]
        task["dependency_evidence_file"] = graph_path.name
        task["dependency_ready_ps"] = {str(parent): transfer_by_id[parent]["receiver_ready_ps"]
                                       for parent in task["dependencies"]}
        require(all(ready <= task["submit_ps"] for ready in task["dependency_ready_ps"].values()),
                "Critical transfer submitted before an actual dependency was ready")
        coverage = sorted((row["offset"], row["offset"] + row["bytes"])
                          for row in transfers if row["physical"] == task["physical"]
                          and row["receiver_ready_ps"] <= end)
        covered_end = 0
        for left, right in coverage:
            require(left <= covered_end, "Hole in final physical receiver coverage")
            covered_end = max(covered_end, right)
        task["physical_received_coverage_bytes"] = covered_end
        task["physical_received_coverage_parts"] = len(coverage)
        chain, events = packet_evidence(tail, task)
        task["packet_chain"] = chain
        # These are observations only. Do not turn observed sequence state or
        # query counts into a continuous window/ACK wait-duration estimate.
        task["native_eligibility_observations"] = {
            "retained_source_limited_queries_by_reason": {
                str(reason): sum(row["kind"] == 14 and row["node"] == task["source"]
                                 and row["reason"] == reason for row in tail)
                for reason in range(9)},
            "retained_source_ack_before_count": sum(row["kind"] == 15
                and row["node"] == task["source"] for row in tail),
            "retained_source_ack_after_count": sum(row["kind"] == 16
                and row["node"] == task["source"] for row in tail),
            "scope": "bounded frozen tail; not complete history or continuous waiting"}
        task["source_weight_phase_cohorts"] = aggregate_metrics(
            [row for row in cohort if row["node"] == task["source"]])
        for i, row in events:
            chosen[i] = row
        matching = [row for row in prefixes if row["node"] == task["source"]
                    and row["last_weight_native_send_ps"] == task["last_native_send_ps"]]
        tx_ports = chain.get("source_tx_ports", [])
        if tx_ports:
            matching = [row for row in matching if row["port"] in tx_ports]
        task["prefix_accounting_candidates"] = matching
        task["post_dequeue_to_ready_ps"] = end - task["last_native_send_ps"]
        task["accounting_unique"] = len(matching) == 1
        task["port_selection_basis"] = "retained_source_tx" if tx_ports else "unique_observed_source_port"
        if len(matching) == 1:
            require(sum(matching[0][key] for key in PARTS) + task["post_dequeue_to_ready_ps"]
                    == end - begin, "Critical source accounting mismatch")
    selected = [{"ring_index": i, "kind_name": KINDS.get(row["kind"], "unknown"), **row}
                for i, row in sorted(chosen.items())]
    require(len(selected) <= 200, "Selected timeline exceeds 200 rows; manually narrow before export")
    return {"weights_start_ps": begin, "weights_end_ps": end, "weight_span_ps": end - begin,
            "status": status, "critical_transfers": critical,
            "excluded_unmeasured_phase_rows": unmeasured_ports,
            "measured_port_keys": sorted({(row["node"], row["port"]) for row in ports if row["total_ps"] > 0}),
            "observed_port_keys": sorted({(row["node"], row["port"]) for row in ports}),
            "native_selected_resource_aggregates": aggregate_metrics(native),
            "weight_phase_selected_resource_cohorts": aggregate_metrics(cohort),
            "voq_interval_quality": {
                "observer": "ordered_FIFO" if fifo_observer else "legacy_UID_keyed",
                "whole_run_unmatched_pops": sum(row["count"] for row in native if row["metric"] == 1000),
                "weight_phase_end_cohort_unmatched_pops": sum(row["count"] for row in cohort if row["metric"] == 1000),
                "overlapping_same_queue_uid_pushes_in_frozen_tail": retained_voq_collisions(tail),
                "limitation": ("Ordered FIFO matching checked against UID, queue depth and monotonic time; all integrity counters zero. Cohort durations still overlap and are not clipped occupancy or causal wall-time."
                    if fifo_observer else "Legacy recorder keys VOQ starts by queue and UID; fragments reuse UIDs. Concurrent same-key pushes overwrite starts. Unmatched pops make whole-run and cohort VOQ residence aggregates incomplete/unvalidated, not suitable for causal claims. A zero collision count in the bounded tail does not clear older aggregate history.")},
            "allready_observed_upper_bounds_not_waits": rows(case / "diagnostic-poll-upper-bounds.csv"),
            "unmatched_end_counts": sum(row["count"] for row in native if row["metric"] >= 1000),
            "selected_timeline_rows": len(selected)}, selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Completed private real-3136 directory")
    parser.add_argument("--out", type=Path, help="Private analysis output, default ROOT/analysis")
    parser.add_argument("--check-case", action="store_true",
                        help="Read-only parser check for one completed small case; prints only counts")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.check_case:
        result, selected = analyze_case(root)
        print(json.dumps({"parser_check": "PASS", "critical_transfers": len(result["critical_transfers"]),
                          "selected_rows": len(selected)}))
        return
    ledger = read_json(root / "ledger.json")
    require(ledger["status"] == "PASS", "Formal collection refused until ledger PASS")
    require(ledger["link_gbps"] == 3136, "Wrong formal link rate")
    require(read_json(ledger["stage_a_path"])["status"] == "PASS", "Stage A not PASS")
    require(sha(ledger["stage_a_path"]) == ledger["stage_a_sha256"], "Stage A identity changed")
    for identity in ledger["identities"].values():
        check_identity(identity)
    source = Path(__file__).with_name("layer.cc")
    source_lines = source.read_text().splitlines()
    cc_lines = [i + 1 for i, line in enumerate(source_lines)
                if 'GlobalValue::Bind("UB_CC_ENABLED",BooleanValue(false))' in line]
    require(len(cc_lines) == 1, "Accepted CC configuration requires fresh review")
    report = {"status": "PASS", "publication_status": "PRIVATE_REVIEW_ONLY", "cases": {},
        "accepted_configuration": {"native_cc_enabled": False,
            "cc_source": {"file": str(source), "line": cc_lines[0], "sha256": sha(source)},
            "interpretation": "Native CC/CNP is inactive in this accepted experiment; this is not a claim that native CC is unsupported. CBFC is a separate mechanism."},
        "cautions": ["Resource accounting is not causal intervention evidence.",
        "TX busy includes IFG/NOB; pure serialization is reported separately.",
        "Cohorts are full residence for end-in-phase events or full service for start-in-phase events, not clipped occupancy.",
        "Packet-time sums overlap; never add them to wall-time partitions.",
        "AllReady spans are held observations, not continuously proven blocking.",
        "Uncovered idle is unexplained eligibility; ACK/window attribution remains a hypothesis unless separately supported.",
        "The selected frozen ring is bounded, not complete run history."]}
    timelines = {}
    for mode in MODES:
        record = read_json(root / mode / "run-result.json")
        require(record["status"] == "PASS" and record["exact_baseline_parity"] is True,
                "Formal case not verified PASS: " + mode)
        check_identity(record["baseline_identity"])
        check_identity(record["immutable_files"])
        result, selected = analyze_case(root / mode)
        require(result["voq_interval_quality"]["observer"] == "ordered_FIFO",
                "Formal v3 collection requires the corrected ordered FIFO observer")
        result["accepted_parity"] = check_parity(root / mode, Path(record["baseline"]))
        require({node for node, port in result["observed_port_keys"]} == NODES,
                "Unexpected selected native node set")
        report["cases"][mode] = result
        timelines[mode] = selected
    require(sum(map(len, timelines.values())) <= 200,
            "Combined selected timeline exceeds 200 rows; narrow manually before export")
    chunk, multicast = (report["cases"][mode] for mode in MODES)
    require({row["task"] for row in chunk["critical_transfers"]} == {69657, 69670},
            "Accepted tied chunk dependencies changed")
    require({row["task"] for row in multicast["critical_transfers"]} == {32814},
            "Accepted multicast final dependency changed")
    for case in (chunk, multicast):
        for task in case["critical_transfers"]:
            require(task["bytes"] == task["physical_received_coverage_bytes"] == 18874368
                    and task["offset"] == 0 and not task["dependencies"],
                    "Accepted direct full-expert final dependency changed")
    require(chunk["observed_port_keys"] == multicast["observed_port_keys"], "Asymmetric port coverage")
    require(chunk["weights_start_ps"] == multicast["weights_start_ps"], "Phase starts differ")
    gap = multicast["weights_end_ps"] - chunk["weights_end_ps"]
    require(gap == 164289264, "Accepted WeightReady gap not reproduced")
    report["weight_ready_gap_ps"] = gap
    critical_mc_tasks = {item["task"] for item in multicast["critical_transfers"]}
    group_rows = rows(root / "multicast-v2" / "multicast-groups.csv")
    critical_groups = {row["group"] for row in group_rows if row["task"] in critical_mc_tasks}
    multicast["critical_group_allready_observations"] = [row for row in
        multicast["allready_observed_upper_bounds_not_waits"] if row["group"] in critical_groups]
    multicast["critical_group_grants"] = [row for row in
        rows(root / "multicast-v2" / "diagnostic-groups.csv") if row["group"] in critical_groups]
    report["accepted_configuration"]["observed_multicast_cnp_primary_evaluations"] = sum(
        row["actual_evaluations"] for row in multicast["allready_observed_upper_bounds_not_waits"]
        if row["reason"] == "cnp")
    decompositions = []
    for mc in multicast["critical_transfers"]:
        for cs in chunk["critical_transfers"]:
            if not (mc["accounting_unique"] and cs["accounting_unique"]):
                continue
            delta = {key: mc["prefix_accounting_candidates"][0][key]
                     - cs["prefix_accounting_candidates"][0][key] for key in PARTS}
            delta["post_dequeue_to_ready_ps"] = mc["post_dequeue_to_ready_ps"] - cs["post_dequeue_to_ready_ps"]
            require(sum(delta.values()) == gap, "Gap decomposition does not close")
            decompositions.append({"multicast_task": mc["task"], "chunk_task": cs["task"],
                "signed_delta_ps": delta, "accounting_residual_ps": gap - sum(delta.values()),
                "causal_status": "Accounting only; uncovered idle remains unexplained eligibility"})
    report["critical_source_gap_decompositions"] = decompositions
    report["accounting_available"] = bool(decompositions)
    out = (args.out or root / "analysis").resolve()
    require(out == root or root in out.parents, "Output must remain inside the private formal root")
    out.mkdir(parents=True, exist_ok=True)
    (out / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    for mode, selected in timelines.items():
        if selected:
            with (out / (mode + "-selected-final-packet-timeline.csv")).open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(selected[0]))
                writer.writeheader()
                writer.writerows(selected)
    print(json.dumps({"analysis": str(out / "analysis.json"), "gap_ps": gap,
                      "selected_rows": {mode: len(value) for mode, value in timelines.items()}}))


if __name__ == "__main__":
    main()
