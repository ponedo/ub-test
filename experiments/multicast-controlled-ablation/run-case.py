"""One 4800-second bounded real run, complete online verification, immutable inputs."""
import argparse
import time
from common import *


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('case_id')
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    root, build = args.root.resolve(), args.build.resolve()
    ledger = json.loads((root / 'ledger.json').read_text())
    record = next(row for row in ledger['runs'] if row['case_id'] == args.case_id)
    assert record['status'] == 'PREPARED'
    assert str(build) == ledger['build'] and ledger['link_gbps'] == 3136
    assert record['allocator'] == 'original' and record['window'] in WINDOWS
    directory = root / args.case_id
    started = time.monotonic()

    def identities():
        for identity in ledger['identities'].values():
            check(identity)
        check(record['baseline_identity'])
        check(record['immutable_files'])
        assert sha(ledger['stage_a_path']) == ledger['stage_a_sha256']
        assert json.loads(Path(ledger['stage_a_path']).read_text())['status'] == 'PASS'
        assert sha(ledger['a_decision_path']) == ledger['a_decision_sha256']

    def save():
        write(directory / 'run-result.json', record)

    def stage(cmd, path):
        remaining = 4800 - (time.monotonic() - started)
        assert remaining > 0, '4800 second whole-case wall guard'
        result = run(cmd, path, remaining, case=root)
        assert result['status'] == 'PASS', 'Guard/nonzero: ' + str(path)
        return result

    try:
        identities()
        record['status'] = 'RUNNING'
        save()
        stage([sys.executable, OLD / 'preflight.py', directory, '--graph-tool', build / 'graph-tool'], directory / 'preflight-host')
        cmd = simulator(build, directory, 'on', record['window'], extra=['--payloadBudgetBytes=8589934592', '--weightTaskLimit=1000000'], formal_strategy=record['strategy'])
        record['simulator_host'] = stage(cmd, directory / 'simulator-host')
        save()
        validate(stage, build, directory)
        record['ablation_config'] = validate_config(directory, record['window'], True)
        record['diagnostic_status'] = validate_diagnostics(directory)
        record['semantic_parity_fields'] = semantic_parity(Path(record['baseline']), directory)
        if record['window'] == 512:
            parity(Path(record['baseline']), directory)
            parity(ORIGINAL / 'real-3136' / record['strategy'], directory)
            record['exact_baseline_parity'] = True
        else:
            record['exact_baseline_parity'] = 'not_applicable_window_intervention_changes_timing'
        identities()
        write(directory / 'identity-after.json', dict(identities=ledger['identities'], baseline_identity=record['baseline_identity'], immutable_files=record['immutable_files']))
        record.update(status='PASS', case_wall_seconds=time.monotonic() - started, summary=json.loads((directory / 'online-summary.json').read_text()), metrics=json.loads((directory / 'simulator-metrics.json').read_text()), bounded_tail_note='Tail rows are sampled/bounded; no full wall-time decomposition from incomplete history.')
        save()
        print('VERIFIED', args.case_id, flush=True)
    except BaseException as exc:
        record.update(status='FAIL', failure=str(exc), case_wall_seconds=time.monotonic() - started)
        save()
        raise


if __name__ == '__main__':
    main()
