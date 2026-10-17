#!/usr/bin/env python3
"""Project online evidence into the existing scale collector's aggregate schema.

Inputs contribute static labels and independently preflight-validated dimensions;
all measured times, completions, byte counts, and packet counts come from the run.
This intentionally does not claim offline raw-payload or trace verification.
"""
import argparse
import json
from pathlib import Path


def project(directory, execution_directory=None):
    directory = Path(directory)
    execution = Path(execution_directory or directory)
    config = json.loads((directory / 'config.json').read_text())
    plan = json.loads((directory / 'plan.json').read_text())
    online = json.loads((execution / 'online-summary.json').read_text())
    validation = json.loads((execution / 'validation.json').read_text())
    if validation['status'] != 'PASS':
        raise ValueError('Online validation must pass before projection')
    parameters = config['runtime']
    physical = plan['physical']
    weights = [x for x in config['transfers'] if x['stage'] == 2]
    npus = config['planner_input']['npus']
    loads = [sum(x['quota'] for x in physical if x['rank'] == rank) for rank in range(npus)]
    summary = dict(online)
    summary.update(mode=config['mode'], strategy=config['weight_strategy'],
                   readiness=config['readiness'], npus=npus,
                   tokens=len(config['planner_input']['mapping']),
                   assignments=len(config['assignments']),
                   replicas=sum(x['kind'] == 'replica' for x in physical),
                   max_npu_load=max(loads, default=0), per_npu_load=loads,
                   weight_bytes=online['verified_bytes'][2], weight_WQEs=len(weights),
                   weight_TAs=sum((x['bytes'] + parameters['segment_bytes'] - 1) // parameters['segment_bytes'] for x in weights),
                   weight_send_bytes_per_npu=[sum(x['bytes'] for x in weights if x['source'] == rank) for rank in range(npus)],
                   weight_target_duration_ps=online['timeline']['weights_end'] - online['timeline']['planning_end'],
                   group_chunk_count=online['event_spans'].get('group_chunk_ready', [0, 0, 0])[2],
                   empty=not config['planner_input']['mapping'],
                   validation_method='independent input/plan/graph preflight plus online execution and terminal payload validation')
    times = {}
    for name, stage in (('dispatch', 0), ('combine', 1)):
        start, finish = online['stage_intervals'][stage]
        times[name + '_start_ps'] = start
        times[name + '_end_ps'] = finish
        times[name + '_span_ps'] = finish - start
    intervals = online['compute_intervals']
    start = min((x['start_ps'] for x in intervals), default=online['timeline']['dispatch_gate'])
    finish = max((x['end_ps'] for x in intervals), default=start)
    times.update(compute_start_ps=start, compute_end_ps=finish, compute_span_ps=finish - start)
    return summary, times


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--execution-directory', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--event-spans-out', type=Path)
    args = parser.parse_args()
    summary, times = project(args.directory, args.execution_directory)
    args.out.write_text(json.dumps(summary, indent=2) + '\n')
    if args.event_spans_out:
        args.event_spans_out.write_text(json.dumps(times, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
