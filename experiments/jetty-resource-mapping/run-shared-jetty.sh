#!/usr/bin/env bash
# Application-only ABI-matched probe; never modifies/rebuilds native sources.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
: "${A_ROOT:?set A_ROOT to baseline native checkout with old headers}"
: "${B_ROOT:?set B_ROOT to indexed native checkout with new headers}"
: "${FROZEN_A:?set FROZEN_A to frozen A library directory ending /lib}"
: "${FROZEN_B:?set FROZEN_B to frozen B library directory ending /lib}"
: "${OUT:?set OUT to a new evidence directory}"
# Refuse to erase any prior failure evidence.
if [[ -e "$OUT" ]]; then echo "OUT already exists; choose a fresh evidence directory" >&2; exit 2; fi
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
FROZEN_A=$(cd "$FROZEN_A" && pwd)
FROZEN_B=$(cd "$FROZEN_B" && pwd)
A_ROOT=$(cd "$A_ROOT" && pwd)
B_ROOT=$(cd "$B_ROOT" && pwd)
printf '%s\n' "A_ROOT=$A_ROOT" "B_ROOT=$B_ROOT" "FROZEN_A=$FROZEN_A" "FROZEN_B=$FROZEN_B" > "$OUT/build-inputs.txt"
sha256sum "$HERE/shared-jetty-probe.cc" "$HERE/run-shared-jetty.sh" >> "$OUT/build-inputs.txt"
for side in A B; do
  if [[ "$side" == A ]]; then root=$A_ROOT; lib=$FROZEN_A; else root=$B_ROOT; lib=$FROZEN_B; fi
  git -C "$root" rev-parse HEAD >> "$OUT/build-inputs.txt"
  # Deliberately do not add native/build/lib to either linker search or rpath.
  "${CXX:-c++}" -std=c++20 -O2 -g "$HERE/shared-jetty-probe.cc" -I"$root/build/include" \
    -L"$lib" -Wl,--disable-new-dtags -Wl,-rpath,"$lib" \
    -lns3.44-unified-bus -lns3.44-network -lns3.44-core \
    -o "$OUT/shared-jetty-$side" >"$OUT/$side.build.stdout" 2>"$OUT/$side.build.stderr"
  env -u LD_PRELOAD LD_LIBRARY_PATH="$lib" ldd "$OUT/shared-jetty-$side" >"$OUT/$side.ldd"
  python3 - "$OUT/$side.ldd" "$lib" <<'PY'
import pathlib, sys
text=pathlib.Path(sys.argv[1]).read_text()
assert 'not found' not in text, text
libs=[]
for line in text.splitlines():
    if 'libns3.' not in line: continue
    fields=line.split()
    assert len(fields)>2 and fields[1]==' => '.strip(), line
    resolved=pathlib.Path(fields[2]).resolve()
    assert resolved.parent==pathlib.Path(sys.argv[2]).resolve(), line
    libs.append(fields[0])
assert {'libns3.44-unified-bus.so','libns3.44-core.so','libns3.44-network.so'} <= set(libs), libs
PY
  for mode in single onesegment concurrentmulti; do
    prefix="$OUT/${side}-${mode}"
    if env -u LD_PRELOAD LD_LIBRARY_PATH="$lib" timeout 30 "$OUT/shared-jetty-$side" --mode="$mode" --output="$prefix" >"$prefix.stdout" 2>"$prefix.stderr"; then
      rc=0
    else
      rc=$?
    fi
    printf '%s\n' "$rc" >"$prefix.exit"
  done
done
# This is a known-failure reproduction, not a capability success gate.
# Preserve per-case FAIL/exit=1 and require the precise expected failure.
python3 - "$OUT" <<'PY' | tee "$OUT/reproduction-check.txt"
import csv, pathlib, sys
p=pathlib.Path(sys.argv[1])
for side in ('A','B'):
    for mode in ('single','onesegment','concurrentmulti'):
        stem=p/f'{side}-{mode}'
        text=pathlib.Path(str(stem)+'-summary.txt').read_text()
        rc=int(pathlib.Path(str(stem)+'.exit').read_text())
        if mode!='concurrentmulti':
            assert rc==0 and 'status=PASS\n' in text and 'failures=0\n' in text, (side,mode,rc,text)
        else:
            assert rc==1 and 'status=FAIL\n' in text and 'failures=1\n' in text, (side,rc,text)
            assert 'failure=sender_before_all_target_completions\n' in text, text
            assert 'snd_una=20\nsnd_nxt=20\n' in text, text
            for wqe in (1001,1002,1003,9001):
                assert f'wqe={wqe} size=4128 callbacks=1 received_segments=5 target_completions=5\n' in text, text
            rows=list(csv.DictReader(open(str(stem)+'-events.csv')))
            ssns=[int(r['ssn']) for r in rows if r['event']=='segment_sent' and r['wqe_id']=='1001']
            assert ssns==[0,3,6,9,12],ssns
            cb=[int(r['time_ns']) for r in rows if r['event']=='sender_callback' and r['wqe_id']=='1001']
            late=[int(r['time_ns']) for r in rows if r['event']=='target_complete' and r['wqe_id']=='1001' and r['ssn']=='9']
            assert len(cb)==len(late)==1 and cb[0]<late[0],(cb,late)
            print(f'{side}: known premature-completion failure reproduced; callback {cb[0]} ns < SSN9 completion {late[0]} ns. Eventual byte coverage complete; terminal UNA==NXT alone does not prove all responses were received.')
for mode in ('single','onesegment','concurrentmulti'):
    for suffix in ('-events.csv','-summary.txt','.exit'):
        assert (p/f'A-{mode}{suffix}').read_bytes()==(p/f'B-{mode}{suffix}').read_bytes(), (mode,suffix)
print('EXPECTED_BASELINE_FAILURE_REPRODUCED: controls pass; concurrent multi-WQE capability fails equally in A and B. This is not a capability PASS.')
PY
