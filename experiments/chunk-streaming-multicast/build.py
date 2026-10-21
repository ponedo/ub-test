#!/usr/bin/env python3
"""Prepare then explicitly gate an APP-only build against immutable native libraries."""
import argparse
import os
import re
from common import *


def prepare(args):
    out, native = args.out.resolve(), args.native.resolve()
    require(not out.exists(), 'Fresh build directory required')
    require((native / 'build/lib/libns3.44-unified-bus.so').is_file(), 'Accepted native library unavailable; no native rebuild fallback')
    identity = read(args.accepted_identity)
    check(identity)
    native_keys = [path for path in identity if Path(path).is_relative_to(native)]
    require(any('/build/lib/' in path for path in native_keys), 'Accepted identity lacks loaded native library closure')
    require(str((native / 'build/lib/libns3.44-unified-bus.so').resolve()) in identity, 'Native library is not pinned')
    # Close only actual quoted APP includes; unrelated evolving tests/docs are not
    # compiler inputs and must not invalidate this isolated APP build.
    sources, pending = set(), [H / 'layer.cc']
    while pending:
        path = pending.pop().resolve()
        if path in sources:
            continue
        require(path.is_file(), 'Missing APP include: ' + str(path))
        sources.add(path)
        for name in re.findall(r'^\s*#\s*include\s*"([^"\n]+)"', path.read_text(), re.M):
            local = (path.parent / name).resolve()
            if local.is_file():
                pending.append(local)
            elif not name.startswith('ns3/'):
                raise ValueError('Unresolved quoted APP include: ' + name)
    orchestration = [H / 'build.py', H / 'common.py', E / 'cloudmatrix-bandwidth/guard.py',
                     E / 'qwen-roofline-compute/guard.py', E / 'multicast-token-screening/heartbeat.py']
    identity.update(freeze(list(sources) + orchestration + [args.accepted_identity, args.graph_tool]))
    out.mkdir(parents=True)
    write(out / 'source-identity.json', identity)
    command = ['c++', '-std=c++20', '-O2', '-g', str(H / 'layer.cc'),
               '-I' + str(native / 'build/include'), '-L' + str(native / 'build/lib'),
               '-Wl,--disable-new-dtags', '-Wl,-rpath,' + str(native / 'build/lib'),
               '-lns3.44-unified-bus', '-lns3.44-internet', '-lns3.44-network', '-lns3.44-core',
               '-o', str(out / 'layer')]
    write(out / 'build-plan.json', dict(status='PREPARED', base=BASE, app_only=True, native=str(native),
          app_include_identity=freeze(sources), native_identity=freeze(native_keys), graph_tool=str(args.graph_tool.resolve()), command=command,
          source_identity_sha256=sha(out / 'source-identity.json'), native_rebuild=False))
    print('PREPARED APP-only build; explicit build approval required. No compiler ran.')


def execute(args):
    out = args.out.resolve()
    plan, approval = read(out / 'build-plan.json'), read(args.approval)
    require(approval.get('status') == 'PASS' and approval.get('approved_to_build') is True, 'Build approval missing')
    require(approval.get('build_plan_sha256') == sha(out / 'build-plan.json'), 'Build approval does not bind this exact plan')
    require(plan['source_identity_sha256'] == sha(out / 'source-identity.json'), 'Build source identity drift')
    identity = read(out / 'source-identity.json')
    identity.update(freeze([out / 'build-plan.json', out / 'source-identity.json', args.approval]))
    check(identity)
    resource_admission(out)
    require(not (out / 'status.json').exists(), 'No implicit build retry')
    write(out / 'status.json', dict(status='BUILDING'))
    try:
        result = stage(plan['command'], out / 'layer-build', identity)
        runtime = dict(identity)
        runtime.update(freeze([out / 'layer']))
        write(out / 'runtime-identity.json', runtime)
        write(out / 'provenance.json', dict(status='PASS', base=BASE, app_only=True, native_rebuilt=False,
              build_plan_sha256=sha(out / 'build-plan.json'), application_sha256=sha(out / 'layer'),
              runtime_identity_sha256=sha(out / 'runtime-identity.json'), graph_tool=plan['graph_tool'],
              native_identity=plan['native_identity'], host=result))
        write(out / 'status.json', dict(status='PASS'))
    except BaseException as exc:
        write(out / 'status.json', dict(status='STOPPED', reason=str(exc)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='phase', required=True)
    prep = sub.add_parser('prepare')
    for key in ('out', 'native', 'accepted-identity', 'graph-tool'):
        prep.add_argument('--' + key, type=Path, required=True)
    run = sub.add_parser('execute')
    for key in ('out', 'approval'):
        run.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    prepare(args) if args.phase == 'prepare' else execute(args)

if __name__ == '__main__':
    main()
