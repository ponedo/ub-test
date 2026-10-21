#!/usr/bin/env python3
"""Use frozen APP-only build machinery, rebinding only candidate source root/base."""
from support import *
implementation = load('candidate_v1_build', V1/'build.py')
implementation.H = HERE
implementation.BASE = BASE_V1
original_prepare = implementation.prepare

def prepare(args):
    original_prepare(args)
    out = args.out.resolve()
    identity = read(out / 'source-identity.json')
    identity.update(freeze([HERE / 'support.py', V1 / 'build.py', V1 / 'common.py']))
    write(out / 'source-identity.json', identity)
    plan = read(out / 'build-plan.json')
    plan['source_identity_sha256'] = sha(out / 'source-identity.json')
    write(out / 'build-plan.json', plan)

implementation.prepare = prepare
if __name__ == '__main__':
    implementation.main()
