# Protocol timing and multicast fairness audit

Start with [REPORT.md](REPORT.md). This is a source/configuration audit only. No simulator source, network/compute parameter, protocol, or workload was changed, and no new simulation was run.

## Files

- `REPORT.md`: initiator/target event paths, effective delays, WRITE Response/completion, byte accounting, configuration differences and A/B integration recommendation.
- `effective-config-evidence.json`: safe runtime projection of 27 completed real-Qwen cases, with verified input/config hashes and simulator flags. No private routing rows are included.
- `source-anchor-checks.json`: 46 checked source/function/range anchors. They verify source location and hash, not dynamic timing or universal semantic equivalence.
- `validation.json`: actual read-only checks, no-source-change result and independent review.

## Source reconstruction and read-only reproduction

The native baseline is `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b` plus the two already published patches in `../ub-network-multicast-poc/patches/`. Use an existing reconstructed checkout, or reconstruct a separate disposable checkout using the instructions in that delivery. Do not run its `reproduce.sh` merely to read this audit: that script also builds and runs the old test suite, which this audit did not do.

In the report, `N/` means the reconstructed native root and `P/` means the outer `ponedo/ub-test` project. Source range hashes join the selected lines with LF, without a final LF. A local source-anchor check can be reproduced without executing the simulator:

```sh
export NATIVE=/path/to/reconstructed/ns-3-ub
export PROJECT=/path/to/ub-test
python3 - <<'PY'
import hashlib,json,os
from pathlib import Path
p=Path(os.environ['PROJECT'])/'experiments/ub-multicast-protocol-timing-audit'
rows=json.loads((p/'source-anchor-checks.json').read_text())['anchors']
for row in rows:
    base=Path(os.environ['NATIVE'] if row['root']=='N' else os.environ['PROJECT'])
    lines=(base/row['path']).read_text().splitlines()
    text='\n'.join(lines[row['start_line']-1:row['end_line']])
    assert row['required_anchor'] in text, row
    assert hashlib.sha256(text.encode()).hexdigest()==row['range_sha256'], row
print('PASS',len(rows),'source anchors')
PY
```

Historical configuration verification reads the private, already finalized tar-xz archives named by each case's `prepared-evidence/manifest.json`. Verify concatenated-part archive SHA256, then the bytes of `run/config.json` and `run/input.txt` against that manifest. Export only `runtime`, the two non-routing scalar header lines, and simulator options excluding private paths. The committed JSON contains those projections and hashes for 27 cases. Raw archives and full configs are intentionally not distributed: they contain restricted routing records. Public readers can verify source anchors and the published projections; independent reinspection of raw inputs requires the authorized private dataset/artifacts.

## Boundaries

No performance estimate is presented as an ns-3 measurement. Zero configured endpoint delays do not imply zero real hardware cost, or that protocol packets/windows may be removed without changing simulated time. Native response receipt, target readiness, layer end and final state drain are distinct events. Recommended future adapter changes are not implemented in this delivery.
