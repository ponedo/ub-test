"""Freeze the six authorized real cases without regenerating any workload input."""
import argparse
from common import *


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--stage-a', type=Path, required=True)
    parser.add_argument('--a-decision', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build, gate_path = args.build.resolve(), args.stage_a.resolve() / 'status.json'
    gate = json.loads(gate_path.read_text())
    assert gate['status'] == 'PASS', 'Small regression gate must pass first'
    for identity in gate['identities'].values():
        check(identity)
    check(gate['input_identity'])
    decision_path = args.a_decision.resolve()
    decision = json.loads(decision_path.read_text())
    assert decision['status'] in ['STOPPED', 'UNSUPPORTED'], 'A requires its own approved implementation and gates; this manifest cannot run it'
    assert decision.get('reason'), 'An explicit A stopping reason is mandatory'
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    ledger = dict(status='PREPARED', link_gbps=3136, build=str(build), stage_a_path=str(gate_path), stage_a_sha256=sha(gate_path), a_decision_path=str(decision_path), a_decision_sha256=sha(decision_path), identities=gate['identities'], runs=[], stopped_runs=[])
    for window in WINDOWS:
        for strategy in REAL_STRATEGIES:
            block = 'baseline-512' if window == 512 else 'window-' + str(window)
            case_id = block + '-' + strategy
            source = ACCEPTED / 'real-3136' / strategy
            directory = out / case_id
            copy_inputs(source, directory)
            baseline = json.loads((source / 'run-result.json').read_text())
            assert baseline['status'] == 'PASS'
            cfg = json.loads((directory / 'config.json').read_text())
            assert all(cfg[x]['link_gbps'] == 3136 for x in ['runtime', 'parameters'])
            assert (directory / 'input.txt').read_text().split()[12] == '3136'
            for name in INPUTS:
                assert (directory / name).read_bytes() == (ORIGINAL / 'real-3136' / strategy / name).read_bytes(), 'Accepted input drift: ' + name
            evidence = freeze([source / name for name in INPUTS + ['online-summary.json', *EXACT, 'run-result.json', 'validation.json', 'network-resources.csv', 'pair-state.csv']])
            ledger['runs'].append(dict(case_id=case_id, block=block, strategy=strategy, window=window, allocator='original', diagnostic=True, status='PREPARED', baseline=str(source), baseline_identity=evidence, immutable_files=freeze([directory / name for name in INPUTS])))
    for strategy in REAL_STRATEGIES:
        ledger['stopped_runs'].append(dict(case_id='null-grant-A-' + strategy, block='A', strategy=strategy, window=512, status=decision['status'], reason=decision['reason'], measured=False))
    write(out / 'identity-before.json', dict(identities=ledger['identities'], inputs={row['case_id']: row['immutable_files'] for row in ledger['runs']}, baselines={row['case_id']: row['baseline_identity'] for row in ledger['runs']}))
    write(out / 'ledger.json', ledger)
    print('PREPARED six independent cases; A recorded as ' + decision['status'])


if __name__ == '__main__':
    main()
