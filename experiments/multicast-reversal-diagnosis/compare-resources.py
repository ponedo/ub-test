"""Private same-physical-resource controls; no simulator launch or source edits."""
import argparse
import csv
import json
from pathlib import Path


def read_rows(path):
    with path.open(newline="") as stream:
        return [{key: int(value) if value.isdecimal() else value for key, value in row.items()}
                for row in csv.DictReader(stream)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    ledger = json.loads((root / "ledger.json").read_text())
    if ledger["status"] != "PASS":
        raise ValueError("Refuse collection until both formal cases PASS")
    selected = [(3, 0), (36, 0), (50, 0), (64, 17), (64, 27), (64, 59)]
    report = {"publication_status": "PRIVATE_REVIEW_ONLY", "resources": [], "semantics": [
        "Same physical node/port in both strategies, not a substituted critical source.",
        "Weight-phase spans end at different strategy WeightReady times; whole-phase idle can include time after this resource's last weight dequeue.",
        "Source-own-last-dequeue partitions use that source's own endpoint, not necessarily the critical transfer or terminal WeightReady.",
        "Source last dequeue is not physical TX completion; post-dequeue phase duration is not all idle.",
        "Residence end-event cohorts contain full residence, not clipped occupancy; service starts and outcome ends have different boundary membership.",
        "Cohort sums overlap and are not wall-time attribution. Legacy v2 UID residence results remain invalid where unmatched pops were observed."]}
    data = {}
    for mode in ("chunk-streaming", "multicast-v2"):
        directory = root / mode
        result = json.loads((directory / "run-result.json").read_text())
        if result["status"] != "PASS" or not result.get("exact_baseline_parity"):
            raise ValueError("Case is not verified PASS: " + mode)
        data[mode] = {"phase": read_rows(directory / "diagnostic-port-partition.csv"),
                      "prefix": read_rows(directory / "diagnostic-source-last-send-partition.csv"),
                      "cohorts": read_rows(directory / "diagnostic-weight-phase-cohorts.csv"),
                      "status": json.loads((directory / "diagnostic-status.json").read_text())}
    for node, port in selected:
        item = {"node": node, "port": port, "strategies": {}}
        for mode, files in data.items():
            matching = lambda key: [row for row in files[key] if row["node"] == node and row["port"] == port]
            phase, prefix, cohorts = matching("phase"), matching("prefix"), matching("cohorts")
            state = {"weight_phase_partition": phase[0] if phase else None,
                     "source_own_last_dequeue_partition": prefix[0] if prefix else None,
                     "weight_phase_cohorts": cohorts,
                     "residence_observer": "ordered_FIFO" if "queue_observations_open" in files["status"] else "legacy_UID_keyed"}
            if phase and prefix:
                state["last_source_dequeue_to_strategy_weight_ready_ps"] = phase[0]["phase_end_ps"] - prefix[0]["last_weight_native_send_ps"]
            item["strategies"][mode] = state
        report["resources"].append(item)
    output = root / "analysis"
    output.mkdir(exist_ok=True)
    destination = output / "same-resource-comparison.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(destination)


if __name__ == "__main__":
    main()
