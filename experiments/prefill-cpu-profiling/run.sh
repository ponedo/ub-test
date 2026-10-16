#!/usr/bin/env bash
# End-to-end fresh-workspace reproduction. Does not overwrite prior runs.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd); WORK=$(dirname "$REPO")
export PATH="$WORK/prefill-cpu-tools/bin:$PATH" PYTHONPATH="$WORK/prefill-cpu-tools${PYTHONPATH:+:$PYTHONPATH}"
test ! -e "$WORK/prefill-cpu-raw"
# A fresh raw directory alone is insufficient: do not append to delivered ledgers.
if [ -d "$HERE/evidence" ]; then
 PREVIOUS="$WORK/prefill-cpu-previous-evidence-$(date -u +%Y%m%dT%H%M%S)"
 test ! -e "$PREVIOUS"
 mv "$HERE/evidence" "$PREVIOUS"
 mkdir -p "$HERE/evidence"
 # Source-provenance only, never previous measurements/checks/ledgers.
 if [ -f "$PREVIOUS/imported-original-build-audit.json" ]; then cp "$PREVIOUS/imported-original-build-audit.json" "$HERE/evidence/"; fi
else
 mkdir -p "$HERE/evidence"
fi
printf '[]\n' > "$HERE/evidence/run-ledger.json"
python3 -c 'import sys,json; from pathlib import Path; sys.path.insert(0,sys.argv[1]); from guard import snapshot; Path(sys.argv[1]+"/evidence/initial-host.json").write_text(json.dumps(snapshot(),indent=2)+"\n")' "$HERE"
bash "$HERE/build.sh"
bash "$HERE/setup_perf.sh" "$WORK/prefill-perf-tools"
mkdir -p "$WORK/prefill-cpu-raw/home"
cc -O2 -g -fno-omit-frame-pointer "$HERE/calibration-hotloop.c" -o "$WORK/prefill-cpu-raw/calibration-hotloop"
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 HOME="$WORK/prefill-cpu-raw/home" "$HERE/record" "$HERE/evidence/calibration2.data" 99 -- "$WORK/prefill-cpu-raw/calibration-hotloop" > "$HERE/evidence/calibration2-console.txt" 2>&1
"$WORK/prefill-perf-tools/perf" report -i "$HERE/evidence/calibration2.data" --stdio --no-children --percent-limit 0 --sort dso,symbol > "$HERE/evidence/calibration2-report.txt"
python3 "$HERE/calibration_check.py" --perf "$WORK/prefill-perf-tools/perf"
python3 "$HERE/parity.py"
for a in 5000 10000 20000 50000; do
 for variant in baseline sampled timed; do python3 "$HERE/execute.py" --assignments "$a" --variant "$variant"; done
done
python3 "$HERE/freeze_symbols.py"
python3 "$HERE/analyze.py" --perf "$WORK/prefill-perf-tools/perf"
python3 "$HERE/ack-attribution.py"
python3 "$HERE/external_phases.py"
python3 "$HERE/compare_original_inputs.py"
python3 "$HERE/check.py"
python3 "$HERE/regressions.py"
python3 "$HERE/report.py"
# Packaging is a separate explicit step after inspecting publication scan results.
