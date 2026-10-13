#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
build=${BUILD_DIR:-build-ingress}
out=${RESULT_DIR:-experiments/ingress/output}
regression=${REGRESSION_DIR:-results/ingress-regression}
mkdir -p "$out"
BUILD_DIR="$build" RESULT_DIR="$regression" bash scripts/run_phase2.sh > "$out/phase2_regression.txt" 2>&1
TRACE_BINARY="$build/trace_e2e" python3 -m unittest discover -s tests/ingress -v > "$out/ingress_tests.txt" 2>&1
python3 - "$regression" "$out" <<'PY'
import hashlib,json,sys
from pathlib import Path
baseline=Path('experiments/phase2/output');rerun=Path(sys.argv[1]);checks=[]
for name in ['systemc.events.csv','systemc.wr.csv']:
    for old in sorted(baseline.glob('*/*/'+name)):
        relative=old.relative_to(baseline);new=rerun/relative
        assert old.read_bytes()==new.read_bytes(),str(relative)
        checks.append({'path':str(relative),'sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'exact':True})
assert len(checks)==42,len(checks)
(Path(sys.argv[2])/'phase2_projection.json').write_text(json.dumps(checks,indent=2)+'\n')
PY
python3 -m experiments.ingress.run --binary "$build/trace_e2e" --output "$out" | tee "$out/experiment_validation.txt"
python3 -m experiments.ingress.audit "$out" | tee "$out/audit_validation.txt"
printf '%s\n' 'PASS: unchanged Phase2 tests/results + 11 ingress tests + 36 simulations + compressed-event audit'
