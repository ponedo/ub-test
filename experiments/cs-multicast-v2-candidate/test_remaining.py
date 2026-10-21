#!/usr/bin/env python3
"""Pure metadata checks against a preserved completed-prefix attempt."""
import argparse
import copy
from unittest.mock import patch
import prepare_remaining as remaining


def check(prior):
    original=remaining.read
    manifest,ledger,identity,rows=remaining.validate(prior)
    assert len(rows)==11 and sum(len(r['executions']) for r in rows)==19
    for mutate in [lambda x:x.update(status='PASS'),lambda x:x.update(reason='resource failure'),
                   lambda x:x['rows'][-1]['executions'][-1]['coverage'].update(stale_grant=True),
                   lambda x:x['rows'][0].update(status='INCOMPLETE')]:
        changed=copy.deepcopy(ledger);mutate(changed)
        def read(path):
            return changed if remaining.Path(path).name=='ledger.json' else original(path)
        with patch.object(remaining,'read',read):
            try:remaining.validate(prior)
            except ValueError:pass
            else:raise AssertionError('Invalid preserved prefix was accepted')
    print('PASS metadata-only helper check plus4 refusal mutations; no output or simulator created')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',type=remaining.Path,required=True)
    check(p.parse_args().prior)
