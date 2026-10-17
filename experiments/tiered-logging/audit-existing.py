#!/usr/bin/env python3
"""Recheck retained representative evidence without re-executing simulations."""
import argparse
import importlib.util
from pathlib import Path
from common import MODES, account_files, read_json, require, sha, write_json

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('tiered_runner', HERE / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = read_json(args.results)
    require(report['status'] == 'PASS', 'Original suite did not pass')
    require(sha(report['binary']) == report['binary_sha256'], 'Tested binary has changed')
    require(sha(report['old_binary']) == report['old_binary_sha256'], 'Reference binary has changed')
    for row in report['runs'] + report['faults']:
        sizes = {name: value['bytes'] for name, value in row['output']['files'].items()}
        for name, size in sizes.items():
            require((Path(row['run_path']) / name).stat().st_size == size, 'Retained measured file changed: ' + name)
        row['output'] = account_files(sizes)
    for case in report['cases']:
        rows = [row for row in report['runs'] if row['case'] == case['name'] and row['mode'] in MODES]
        fresh = runner.verify_modes(rows)
        report['comparisons'][case['name']].update(fresh)
        if case['name'] == 'multichunk-multita':
            summary = next(row for row in rows if row['mode'] == 'debug')['strict_summary']
            require(summary['group_chunk_count'] > 1, 'No actual multichunk work')
            require(case['dimensions']['max_TAs_per_WQE'] > 1, 'No actual multi-TA WQE')
            require(summary['pipeline_overlaps'] and summary['native_pipeline_overlaps'], 'No actual pipeline overlap')
            report['comparisons'][case['name']]['multichunk_multita_proof'] = {
                'group_chunks': summary['group_chunk_count'],
                'max_TAs_per_WQE': case['dimensions']['max_TAs_per_WQE'],
                'application_pipeline_overlaps': len(summary['pipeline_overlaps']),
                'native_pipeline_overlaps': len(summary['native_pipeline_overlaps'])}
    require(len(report['faults']) == len(runner.FAULTS) * len(MODES), 'Incomplete fault matrix')
    for row in report['faults']:
        require(row['status'] == 'PASS' and row['host']['guard'] is None and row['host']['returncode'] > 0,
                'Fault was not an expected positive nonzero exit')
        require(read_json(Path(row['run_path']) / 'validation.json')['status'] == 'FAIL', 'Fault lacks FAIL validation')
    report['retained_evidence_audit'] = {'status': 'PASS', 'reexecuted': False,
                                       'scope': 'stable summaries, independently reconstructed key events, measured-file accounting, pipeline fixture proof and fault coverage'}
    write_json(args.out, report)
    print('PASS retained evidence audit:', args.out)


if __name__ == '__main__':
    main()
