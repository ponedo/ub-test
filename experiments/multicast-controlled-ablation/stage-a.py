"""Fail-closed small correctness, default parity, per-window observer parity, and bounds gate."""
import argparse
from collections import Counter
from common import *


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build, out = args.build.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    identities = build_identities(build)
    inputs = freeze([ORIGINAL / 'stage-a' / fixture / str(rate) / strategy / name for fixture in FIXTURES for rate in [100, 3136] for strategy in STRATEGIES for name in INPUTS + ['online-summary.json', *EXACT]])
    write(out / 'identity-before.json', dict(**identities, input_identity=inputs))
    rows = []
    counts = Counter()

    def stage(cmd, path, negative=None):
        result = run(cmd, path, 1800, case=out)
        if negative:
            assert result['returncode'] != 0 and not result['guard'], 'Negative case failed for wrong reason: ' + str(path)
            assert negative in (path / 'console.txt').read_text(), 'Missing rejection: ' + negative
        else:
            assert result['status'] == 'PASS', 'Guard/nonzero: ' + str(path)
        return result

    def add(category, directory, window, mode, **extra):
        rows.append(dict(category=category, case=str(directory.relative_to(out)), window=window, variant=mode, status='PASS', **extra))
        counts[category] += 1
        write(out / 'results.json', rows)

    def group(source, base, window, fault=None, model='roofline', category='small', extra=()):
        modes = MODES if window == 512 else ['off', 'on']
        for mode in modes:
            directory = base / mode
            copy_inputs(source, directory)
            stage([sys.executable, OLD / 'preflight.py', directory, '--graph-tool', build / 'graph-tool'], directory / 'preflight-host')
            flags = (['--invalidateGrant=1'] if fault == 'invalidate-grant' else ['--nativeRetrans=1', '--networkFault=' + fault]) if fault else []
            cmd = simulator(build, directory, mode, window, events=True, extra=[*flags, *extra], explicit_window=(window != 512 or mode != 'off'))
            cmd = [('--computeModel=' + model) if str(value).startswith('--computeModel=') else value for value in cmd]
            stage(cmd, directory / 'simulator-host')
            validate(stage, build, directory, fault, model)
            if mode != 'accepted':
                validate_config(directory, window, mode == 'on')
            if mode == 'on':
                validate_diagnostics(directory)
            if mode != modes[0]:
                parity(base / modes[0], directory, events=True)
            if mode == 'accepted' and not fault and not extra:
                original, current = summary(source), summary(directory)
                assert original['log_level'] == 'summary' and current['log_level'] == 'events'
                original['log_level'] = 'events'
                assert original == current, 'Accepted baseline changed beyond requested log level'
                for name in EXACT:
                    assert (source / name).read_bytes() == (directory / name).read_bytes(), 'Accepted baseline evidence changed: ' + name
            if window != 512 and not fault:
                semantic_parity(source, directory)
            add(category, directory, window, mode, fault=fault, compute_model=model)

    try:
        for name in ['observer-fifo-test', 'jetty-window-test', 'jetty-observer-test']:
            stage([build / name], out / (name + '-host'))
        for window in WINDOWS:
            for fixture in FIXTURES:
                for rate in [100, 3136]:
                    for strategy in STRATEGIES:
                        source = ORIGINAL / 'stage-a' / fixture / str(rate) / strategy
                        group(source, out / 'small' / str(window) / fixture / str(rate) / strategy, window)
        source = ORIGINAL / 'stage-a/multi-target/3136/multicast-v2'
        for window in WINDOWS:
            for fault in ['data-once', 'ack-once', 'invalidate-grant']:
                for model in ['legacy', 'roofline']:
                    group(source, out / 'network' / str(window) / model / fault, window, fault, model, 'fault')
        for window in WINDOWS:
            for fault, reason in [('weight-byte', 'payload byte mismatch'), ('early-wqe', 'sender completed before target data ready'), ('premature-ready', 'ready before target completion coverage'), ('duplicate-completion', 'audit premature/duplicate sender completion')]:
                for mode in MODES if window == 512 else ['off', 'on']:
                    directory = out / 'negative' / str(window) / fault / mode
                    copy_inputs(source, directory)
                    stage(simulator(build, directory, mode, window, True, ['--fault=' + fault]), directory / 'simulator-host', reason)
                    add('negative', directory, window, mode)
        for rate in ['100.5', '100junk', '100 junk', '1e2', '-1', '0', '18446744073709551616']:
            for mode in MODES:
                directory = out / 'invalid-rate' / rate / mode
                copy_inputs(source, directory)
                stage(simulator(build, directory, mode, extra=['--compute-tflops=' + rate]), directory / 'simulator-host', 'ERROR:')
                add('invalid_rate', directory, 512, mode)
        for window_text in ['0', '1', '511', '513', '1023', '1025', '2047', '2049', '-1', '512.0', '512junk', '512 junk', '5.12e2', '18446744073709551616', '']:
            for mode in ['off', 'on']:
                directory = out / 'invalid-window' / (window_text or 'empty') / mode
                copy_inputs(source, directory)
                cmd = simulator(build, directory, mode, explicit_window=False, extra=['--jetty-ta-window=' + window_text])
                stage(cmd, directory / 'simulator-host', 'ERROR:')
                add('invalid_window', directory, window_text, mode)
        for flag, value, reason in [('payloadBudgetBytes', '0', 'payload budget range'), ('payloadBudgetBytes', '8589934593', 'payload budget range'), ('payloadBudgetBytes', '1', 'payload bound'), ('weightTaskLimit', '0', 'weight task limit range'), ('weightTaskLimit', '1000001', 'weight task limit range'), ('weightTaskLimit', '1', 'weight task count bound')]:
            for mode in ['off', 'on']:
                directory = out / 'invalid-capacity' / (flag + '-' + value) / mode
                copy_inputs(source, directory)
                stage(simulator(build, directory, mode, extra=['--' + flag + '=' + value]), directory / 'simulator-host', reason)
                add('invalid_capacity', directory, 512, mode)
        for window in WINDOWS:
            group(source, out / 'max-capacity' / str(window), window, category='max_capacity', extra=['--payloadBudgetBytes=8589934592', '--weightTaskLimit=1000000'])
        assert (ROOF / 'compute-model.h').read_bytes() == (ROOT / 'bandwidth-work/experiments/qwen-roofline-compute/compute-model.h').read_bytes()
        stage([sys.executable, ROOF / 'test-model.py', ORIGINAL / 'build/model-probe', out / 'model-unit'], out / 'model-unit-host')
        for fixture in FIXTURES:
            for strategy in STRATEGIES:
                source = ORIGINAL / 'stage-a' / fixture / '100' / strategy
                base = out / 'legacy' / fixture / strategy
                for mode in ['parent', *MODES]:
                    directory = base / mode
                    copy_inputs(source, directory)
                    cmd = simulator(build, directory, 'accepted' if mode == 'parent' else mode, events=True)
                    cmd = [x for x in cmd if not str(x).startswith('--computeModel=')]
                    if mode == 'parent':
                        cmd[0] = ORIGINAL / 'build/parent-layer'
                        cmd = [x for x in cmd if not str(x).startswith(('--compute-tflops=', '--hbm-bandwidth-gbps='))]
                    else:
                        cmd += ['--computeModel=legacy']
                    stage(cmd, directory / 'simulator-host')
                    stage([sys.executable, OLD / 'preflight.py', directory, '--graph-tool', build / 'graph-tool', '--execution-summary', directory / 'online-summary.json'], directory / 'postflight-host')
                    stage([sys.executable, OLD / 'verify.py', directory], directory / 'independent-host')
                    if mode != 'parent':
                        stage([sys.executable, ROOF / 'verify-compute.py', directory, '--expected-model=legacy'], directory / 'compute-host')
                        assert summary(base / 'parent') == summary(directory), 'Legacy parent mismatch'
                        assert (base / 'parent/events.csv').read_bytes() == (directory / 'events.csv').read_bytes(), 'Legacy parent event mismatch'
                    if mode in ['off', 'on']:
                        parity(base / 'accepted', directory, True)
                        validate_config(directory, 512, mode == 'on')
                    if mode == 'on':
                        validate_diagnostics(directory)
                    add('legacy', directory, 512, mode)
        assert counts == Counter(small=224, fault=42, negative=28, invalid_rate=21, invalid_window=30, invalid_capacity=12, max_capacity=7, legacy=64), 'Incomplete regression matrix: ' + str(counts)
        for identity in identities.values():
            check(identity)
        check(inputs)
        write(out / 'identity-after.json', dict(**identities, input_identity=inputs))
        write(out / 'status.json', dict(status='PASS', counts=dict(counts), model_unit_pass=True, observer_fifo_test_pass=True, native_window_boundary_test_pass=True, jetty_observer_unit_test_pass=True, queue_observer_invariants_pass=True, jetty_observer_invariants_pass=True, event_order='EXACT accepted/OFF/ON at 512; EXACT OFF/ON independently at 1024 and 2048', summary='EXACT excluding only verification_wall_ns for equal-window pairs', identities=identities, input_identity=inputs))
        print('PASS controlled-ablation small gates', dict(counts), flush=True)
    except BaseException as exc:
        write(out / 'status.json', dict(status='FAIL', failure=str(exc), counts=dict(counts)))
        raise


if __name__ == '__main__':
    main()
