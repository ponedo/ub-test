#!/usr/bin/env python3
"""Strict native-suite gate; the known examples failure remains FAIL."""
import json, subprocess, sys
from pathlib import Path
if not __debug__:
    raise RuntimeError("Assertions must remain enabled")

def validate(rows, expected, outer, console, parser_exists):
    assert not outer.get('guard'), 'outer resource guard'
    assert len(expected) == len(set(expected)) and expected, 'invalid suite inventory'
    assert [x['suite'] for x in rows] == expected, 'incomplete or reordered suite inventory'
    assert all(not x.get('guard') for x in rows), 'inner resource guard'
    failed = [x for x in rows if x['status'] != 'PASS']
    assert all(x['returncode'] == 0 for x in rows if x['status'] == 'PASS'), 'inconsistent PASS'
    assert outer['returncode'] == (1 if failed else 0), 'runner exit mismatch'
    if failed:
        assert len(failed) == 1 and failed[0]['suite'] == 'unified-bus-examples', 'unexpected failure'
        assert failed[0]['status'] == 'FAIL' and failed[0]['returncode'] == 1, 'abnormal examples exit'
        assert not parser_exists, 'missing-parser exception not applicable'
        failures = [s.strip() for s in console.splitlines() if s.strip().startswith('FAIL ')]
        assert len(failures) == 2 and failures[0].startswith('FAIL unified-bus-examples '), 'unexpected test failure count'
        assert failures[1].startswith('FAIL UnifiedBus - ub-quick-example local dependency visibility delay applies '), 'unexpected failed test'
        assert 'test="hasTaskTimes (actual) == true (limit)" actual="0" limit="1"' in console, 'different assertion'
        assert 'dependent tasks should have start/finish times' in console, 'different diagnostic'
    return [x['suite'] for x in failed]

if __name__ == '__main__':
    n,o = map(Path, sys.argv[1:])
    expected = [x for x in subprocess.check_output([n/'build/utils/ns3.44-test-runner','--list'],text=True).splitlines() if x.startswith('unified-bus')]
    rows = json.loads((o/'native-tests/summary.json').read_text())
    outer = json.loads((o/'native-tests-host/resource.json').read_text())
    p = o/'native-tests/unified-bus-examples/console.txt'
    failures = validate(rows,expected,outer,p.read_text() if p.exists() else '',(n/'scratch/ns-3-ub-tools/trace_analysis/parse_trace.py').exists())
    print('Native suite failures retained as FAIL:',failures)
