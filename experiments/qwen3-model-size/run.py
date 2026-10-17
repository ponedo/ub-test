#!/usr/bin/env python3
"""Sequential scale gates with summary-default online validation and fixed guards.

Debug explicitly retains the original raw evidence and strict offline verifier.
Summary/events run the same simulator model and independently validate inputs,
plans and executed graph; only persistence and offline evidence volume differ.
"""
import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parent / 'ep64-token-scaling'))
sys.path.insert(0, str(H.parent / 'wqe-completion-fix'))
sys.path.insert(0, str(H.parent / 'tiered-logging'))
from guard import run, snapshot
from common import INPUTS, event_evidence, size_breakdown
from compact import compact, sha
from restore import restore

spec = importlib.util.spec_from_file_location('tiered_summary_projection', H.parent / 'tiered-logging/project-summary.py')
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--raw', type=Path, required=True)
p.add_argument('--binary', type=Path, required=True)
p.add_argument('--lib', type=Path, required=True)
p.add_argument('--graph-tool', type=Path, required=True)
p.add_argument('--reference-raw', type=Path)
p.add_argument('--reuse-prepared', action='store_true', help='Restore exact prepared inputs from --reference-raw, including historical planner timing metadata')
p.add_argument('--tokens', type=int, nargs='+', default=[256, 1024, 2048, 4096, 6250, 8192, 12500])
p.add_argument('--log-level', choices=['summary', 'events', 'debug'], default='summary')
a = p.parse_args()
raw = a.raw.resolve()
raw.mkdir(parents=True, exist_ok=True)
assert a.tokens == sorted(set(a.tokens)) and set(a.tokens) <= {256, 1024, 2048, 4096, 6250, 8192, 12500}
assert not a.reuse_prepared or a.reference_raw, '--reuse-prepared requires --reference-raw'
references = json.loads((a.reference_raw / 'runs.json').read_text()) if a.reference_raw else []
ledger = []
current_record = None
status = {'status': 'RUNNING', 'completed_token_points': [], 'log_level': a.log_level}
(raw / 'host-start.json').write_text(json.dumps(snapshot(), indent=2) + '\n')
env = {'PATH': str(Path(sys.executable).parent) + ':/usr/bin:/bin', 'LANG': 'C.UTF-8',
       'LD_LIBRARY_PATH': str(a.lib.resolve()), 'RELAY_GRAPH_TOOL': str(a.graph_tool.resolve())}
provenance = {'baseline_configuration': json.loads((H / 'fixed-config.json').read_text()),
              'executor_binary': str(a.binary.resolve()), 'executor_binary_sha256': sha(a.binary.resolve()),
              'executor_source_sha256': {name: sha(H.parent / 'pair-jetty' / name)
                                         for name in ('pair-layer.cc', 'online-validation.inc', 'pair-jetty-manager.h')},
              'native_libraries_sha256': {x.name: sha(x) for x in sorted(a.lib.glob('libns3*.so'))},
              'graph_tool_sha256': sha(a.graph_tool.resolve())}
(raw / 'execution-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')


def persist():
    (raw / 'runs.json').write_text(json.dumps(ledger, indent=2) + '\n')
    (raw / 'status.json').write_text(json.dumps(status, indent=2) + '\n')


def check_guard():
    if shutil.disk_usage(raw).free < 8 * 1024**3:
        raise RuntimeError('disk_free_guard preflight')
    if shutil.disk_usage('/tmp').free < 2 * 1024**3:
        raise RuntimeError('tmp_disk_free_guard preflight')


def checked(command, where):
    check_guard()
    result = run(command, where, 300, case=raw, env=env)
    if result['status'] != 'PASS':
        status.update(failure_resource=str(where / 'resource.json'), failure_measurement=result)
        if current_record is not None:
            current_record.update(status='FAIL', failure_resource=str(where / 'resource.json'),
                                  failure_reason=result['guard'] or 'nonzero_exit')
        raise RuntimeError('stage failed ' + str(where) + ' ' + str(result['guard']))
    return result


try:
    for tokens in a.tokens:
        current_record = None
        check_guard()
        point = raw / f'tokens-{tokens}'
        point.mkdir(exist_ok=False)
        prep = point / 'prepared'
        if a.reuse_prepared:
            source = a.reference_raw / f'tokens-{tokens}' / 'prepared-evidence'
            preparation = {'status': 'RESTORED', 'source': str(source),
                           'integrity': restore(source, prep),
                           'planner_measurement_origin': 'historical prepared-input metadata; planner not rerun'}
        else:
            preparation = checked([sys.executable, str(H / 'prepare.py'), '--tokens', tokens,
                                   '--out', prep, '--graph-tool', a.graph_tool], point / 'preparation-host')
        pm = json.loads((prep / 'preparation-metrics.json').read_text())
        load = json.loads((prep / 'expert-load.json').read_text())
        for name in ['routing.csv', 'expert-load.json', 'preparation-metrics.json']:
            shutil.copy2(prep / name, point / name)
        if a.reference_raw and (a.reference_raw / f'tokens-{tokens}' / 'routing.csv').exists():
            assert sha(prep / 'routing.csv') == sha(a.reference_raw / f'tokens-{tokens}' / 'routing.csv'), 'restart routing changed'
        compact(prep, point / 'prepared-evidence')
        reference, rows = {}, []
        for strategy in ['no-balancing', 'direct', 'chunk-streaming']:
            arm = point / strategy
            dest = arm / 'run'
            restore(point / 'prepared-evidence', dest, prefix=strategy)
            rec = {'tokens': tokens, 'assignments': tokens * 8, 'strategy': strategy, 'log_level': a.log_level,
                   'routing_sha256': pm['shared_routing_sha256'],
                   'input_hashes': {x.name: sha(x) for x in dest.iterdir() if x.is_file()},
                   'expert_load': load, 'preparation_host': preparation,
                   'planner_cpu_wall_seconds': pm['planner_cpu_wall_seconds']['no-balancing' if strategy == 'no-balancing' else 'ultraep'],
                   'execution_provenance': str(raw / 'execution-provenance.json'),
                   'planner_measurement_origin': 'historical prepared-input metadata' if a.reuse_prepared else 'measured preparation in this run'}
            ledger.append(rec)
            current_record = rec
            persist()
            for old in references:
                if old['tokens'] == tokens and old['strategy'] == strategy:
                    assert rec['input_hashes'] == old['input_hashes'], 'restart input bytes changed'
                    (point / (strategy + '-restart-input-parity.json')).write_text(json.dumps(
                        {'status': 'PASS', 'reference_raw': str(a.reference_raw), 'routing_sha256': rec['routing_sha256'],
                         'strategy': strategy, 'old_input_hashes': old['input_hashes'],
                         'new_input_hashes': rec['input_hashes']}, indent=2) + '\n')
            preflight = [sys.executable, str(H.parent / 'tiered-logging/preflight.py'), dest,
                         '--graph-tool', a.graph_tool, '--out', arm / 'preflight.json',
                         '--input-summary', dest / 'input-summary.json', '--provenance', H / 'fixed-config.json']
            rec['preflight_host'] = checked(preflight, arm / 'preflight-host')
            command = [a.binary.resolve(), '--input=' + str(dest / 'input.txt'), '--out=' + str(dest),
                       '--capacityMetrics=' + str(dest / 'simulator-metrics.json'), '--jettyMode=pair',
                       '--logLevel=' + a.log_level,
                       '--payloadBudgetBytes='+str(json.loads((dest/'config.json').read_text())['runtime'].get('payload_budget_bytes',256*1024**2)),
                       '--weightTaskLimit='+str(json.loads((dest/'config.json').read_text())['runtime'].get('weight_task_limit',20000))]
            rec['simulator_host'] = checked(command, arm / 'simulator-host')
            persist()
            rec['online_validation'] = json.loads((dest / 'validation.json').read_text())
            assert rec['online_validation']['status'] == 'PASS', 'Online validation failed'
            rec['verifier_host'] = checked(preflight + ['--execution-summary', dest / 'online-summary.json'],
                                           arm / 'postflight-host')
            rec['preflight_validation'] = json.loads((arm / 'preflight.json').read_text())
            rec['online_summary'] = json.loads((dest / 'online-summary.json').read_text())
            projected, times = projection.project(dest)
            if a.log_level == 'debug':
                rec['strict_verifier_host'] = checked([sys.executable, str(H.parent / 'pair-jetty/verify.py'), dest, 'pair'],
                                                     arm / 'verifier-host')
                rec['summary'] = json.loads((dest / 'summary.json').read_text())
                rec['validation'] = json.loads((dest / 'pair-validation.json').read_text())
                independent = event_evidence(dest / 'events.csv')
                for name in ('dispatch', 'combine', 'compute'):
                    assert independent['stage_spans'][name] == [times[name + '_start_ps'], times[name + '_end_ps'], times[name + '_span_ps']], 'Online/debug stage timing mismatch'
            else:
                rec['summary'] = projected
                rec['validation'] = rec['online_validation']
                (dest / 'summary.json').write_text(json.dumps(projected, indent=2) + '\n')
            rec['metrics'] = json.loads((dest / 'simulator-metrics.json').read_text())
            rec['event_spans'] = times
            rec['output_sizes'] = size_breakdown(dest)
            c = json.loads((dest / 'config.json').read_text())
            plan = json.loads((dest / 'plan.json').read_text())
            rec['plan_load'] = [sum(ph['quota'] for ph in plan['physical'] if ph['rank'] == rank) for rank in range(64)]
            rec['physical_quota_sum'] = sum(ph['quota'] for ph in plan['physical'])
            assert rec['physical_quota_sum'] == tokens * 8
            routing = c['planner_input']['mapping']
            if not reference:
                reference = {'routing': routing, 'plan': None}
            assert routing == reference['routing']
            if strategy == 'direct':
                reference['plan'] = plan
            if strategy == 'chunk-streaming':
                assert plan == reference['plan']
            assert rec['summary']['tokens'] == tokens and rec['summary']['assignments'] == tokens * 8
            rec['status'] = 'PASS'
            persist()
            if a.log_level == 'debug':
                rec['evidence_compaction'] = compact(arm, point / (strategy + '-evidence'))
            else:
                # Keep ordinary aggregate results readable, and archive only these
                # newly materialized, hash-verified input copies. Never touch prior data.
                materialized = arm / 'input-materialized'
                materialized.mkdir()
                for name in INPUTS:
                    if (dest / name).exists():
                        shutil.move(dest / name, materialized / name)
                rec['input_evidence_compaction'] = compact(materialized, arm / 'input-evidence')
            persist()
            rows.append(rec)
            (point / (strategy + '-result.json')).write_text(json.dumps(rec, indent=2) + '\n')
            print('VERIFIED', tokens, strategy, rec['summary']['layer_latency_ps'], a.log_level, flush=True)
        for rec in rows:
            rec['speedup'] = rows[0]['summary']['layer_latency_ps'] / rec['summary']['layer_latency_ps']
            (point / (rec['strategy'] + '-result.json')).write_text(json.dumps(rec, indent=2) + '\n')
        status['completed_token_points'].append(tokens)
        persist()
    status['status'] = 'PASS'
except Exception as error:
    status.update(status='STOPPED', reason=str(error))
    print('STOP', error, flush=True)
finally:
    persist()
if status['status'] != 'PASS':
    sys.exit(2)
