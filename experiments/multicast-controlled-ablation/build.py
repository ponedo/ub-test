"""Build only the isolated ablation application, never accepted executables."""
import argparse
from common import *


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--native', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    native, out = a.native.resolve(), a.out.resolve()
    assert native.name == 'ablation-native' and native != ROOT / 'diagnosis-native'
    out.mkdir(parents=True, exist_ok=False)
    write(out / 'native-delta.json', native_delta(native))
    before = source_identity(native)
    write(out / 'source-identity.json', before)
    accepted = freeze([ACCEPTED / 'build/layer', ACCEPTED / 'build/graph-tool', ORIGINAL / 'build/parent-layer', ORIGINAL / 'build/model-probe', *list((ROOT / 'diagnosis-native/build/lib').glob('*.so')), *list((ROOT / 'bandwidth-native/build/lib').glob('*.so'))])
    write(out / 'accepted-identity.json', accepted)
    cmd = ['c++', '-std=c++20', '-O2', '-g', H / 'layer.cc', '-I' + str(native / 'build/include'), '-L' + str(native / 'build/lib'), '-Wl,--disable-new-dtags', '-Wl,-rpath,' + str(native / 'build/lib'), '-lns3.44-unified-bus', '-lns3.44-internet', '-lns3.44-network', '-lns3.44-core', '-o', out / 'layer']
    assert run(cmd, out / 'layer-build', 1800, case=out)['status'] == 'PASS'
    for name in ['observer-fifo-test', 'jetty-window-test', 'jetty-observer-test']:
        unit = list(cmd)
        unit[unit.index(H / 'layer.cc')] = H / (name + '.cc')
        unit[-1] = out / name
        assert run(unit, out / (name + '-build'), 1800, case=out)['status'] == 'PASS'
    shutil.copyfile(ACCEPTED / 'build/graph-tool', out / 'graph-tool')
    (out / 'graph-tool').chmod(0o755)
    check(before)
    check(accepted)
    write(out / 'binary-identity.json', binaries(out, native))
    write(out / 'status.json', dict(status='PASS', native=str(native)))


if __name__ == '__main__':
    main()
