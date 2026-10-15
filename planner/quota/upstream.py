"""Pinned-source CPU execution and explicitly audited integer-margin repair.

The reference extraction is the execution engine, not a handwritten replacement
for the public replication/search algorithm. CUDA collectives are CPU-adapted.
"""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMMIT = '94cab099b44fffa99a82fea99e7c12d89cf65e4f'


def prepare():
    """Build from pinned source when inputs change; never use an unverified binary."""
    for binary, script, inputs in [
        ('replication_cpu', 'extract_replication.py', ['placement.cu', 'replication_adapter.cpp']),
        ('reference_cpu', 'extract.py', ['placement.cu', 'reroute.cu', 'weight_sync.cu']),
    ]:
        files = [ROOT/'reference'/x for x in [script]+inputs]
        digest = hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest()
        executable = ROOT/'reference'/binary
        stamp = executable.with_suffix('.build.json')
        expected = json.loads(stamp.read_text()) if stamp.exists() else {}
        if (not executable.exists() or expected.get('sources') != digest or
                expected.get('binary') != hashlib.sha256(executable.read_bytes()).hexdigest()):
            subprocess.run(['python3', str(ROOT/'reference'/script)], check=True, capture_output=True, text=True)
            stamp.write_text(json.dumps(dict(sources=digest, binary=hashlib.sha256(executable.read_bytes()).hexdigest()))+'\n')


def replication(c, loads):
    prepare()
    g, e = c['npus'], c['experts']
    stdin = ' '.join(map(str, [g, e//g, c['slots'][0], c['beta'], c['min_replica_quota'],
                              int(c['allow_zero_main']), c['oracle_epsilon'], c['kernel_stage']]+loads))+'\n'
    run = subprocess.run([str(ROOT/'reference/replication_cpu')], input=stdin,
                         capture_output=True, text=True, check=True, timeout=120)
    raw = json.loads(run.stdout)
    # Trace arrival order across fallback warps is not an algorithmic ordering.
    raw['probes'].sort(key=lambda p: (-p['dynamic'], -p['store'], p['threshold']))
    return raw, dict(commit=COMMIT, replication_stdin=stdin, replication_stdout=run.stdout,
                     replication=raw, validation='CPU adapted source execution, not GPU execution')


def repair_margins(raw, demand, hosts, quotas, locality):
    """Move only allocations needed to correct column totals; preserve each row.

    Local fills are locked. Each move fixes one surplus and one deficit column,
    so moved assignments attain the lower bound sum(max(raw_column-U, 0)).
    """
    q = [row.copy() for row in raw]
    if [sum(row) for row in q] != demand:
        raise ValueError('Upstream source margin changed: unsupported, refusing silent repair')
    delta = [sum(row[j] for row in q)-quota for j,quota in enumerate(quotas)]
    minimum_moves = sum(max(x,0) for x in delta)
    moves = []
    for j in range(len(hosts)):
        if delta[j] <= 0:
            continue
        for source in range(len(demand)):
            locked = min(demand[source], quotas[j]) if locality and source == hosts[j] else 0
            removable = q[source][j]-locked
            for k in range(len(hosts)):
                amount = min(delta[j], max(-delta[k],0), removable)
                if amount <= 0:
                    continue
                q[source][j] -= amount
                q[source][k] += amount
                delta[j] -= amount
                delta[k] += amount
                removable -= amount
                moves.append(dict(source=source, from_instance=j, to_instance=k, assignments=amount))
    if any(delta) or sum(m['assignments'] for m in moves) != minimum_moves:
        raise ValueError('Unable to repair upstream margins with minimal local-preserving moves')
    return q, dict(trigger=bool(moves), reason='upstream independent per-source rounding column mismatch' if moves else None,
                   raw=raw, corrected=q, minimum_moved_assignments=minimum_moves, moves=moves)


def decomposition(c, matrix, physical_in_upstream_order):
    """Execute exact fast/slow source blocks in original main-then-export order."""
    g, e = c['npus'], c['experts']
    groups = [[p for p in physical_in_upstream_order if p['expert']==x] for x in range(e)]
    lines = []
    for x, group in enumerate(groups):
        lines.append(' '.join(map(str, [g,len(group),int(c['locality_aware'])]+
                     [matrix[r][x] for r in range(g)]+[p['rank'] for p in group]+[p['quota'] for p in group])))
    stdin = '\n'.join(lines)+'\n'
    run = subprocess.run([str(ROOT/'reference/reference_cpu')], input=stdin,
                         capture_output=True, text=True, check=True, timeout=120)
    rows = [list(map(int,line.split())) for line in run.stdout.splitlines()]
    at = 0
    result, audits = [], []
    for x, group in enumerate(groups):
        raw = rows[at:at+g]; at += g
        if len(group) <= 8:
            fast = rows[at:at+g]; at += g
            if fast != raw:
                raise ValueError('Pinned fast/slow decomposition disagreement: unsupported')
        q, audit = repair_margins(raw, [matrix[r][x] for r in range(g)],
                                 [p['rank'] for p in group], [p['quota'] for p in group], c['locality_aware'])
        audit.update(expert=x, physical_ids=[p['id'] for p in group])
        result.append(q); audits.append(audit)
    if at != len(rows):
        raise ValueError('Unexpected reference decomposition output size')
    return groups, result, dict(decomposition_stdin=stdin, decomposition_stdout=run.stdout,
                               quota_repairs=audits, moved_assignments=sum(a['minimum_moved_assignments'] for a in audits))
