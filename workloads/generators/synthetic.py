"""Independent CPU synthetic WRITE generator. No scheduling decisions."""
import argparse
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from workloads.schema.trace import MAX_INT, canonicalize, integer, make_wr, validate, write_json, write_trace


@dataclass(frozen=True)
class Config:
    jetties: int = 3
    wr_per_jetty: int = 256
    sizes: tuple = (64, 256, 1024)
    src_node: int = 0
    dst_node: int = 1
    arrival: str = 'batch'
    burst_size: int = 8
    burst_gap_ns: int = 1000
    mean_gap_ns: float = 100.0
    start_ns: int = 0
    seed: int = 1


def generate(config):
    c = config
    for name in ('jetties', 'burst_size'):
        integer(getattr(c, name), name, 1)
    for name in ('wr_per_jetty', 'src_node', 'dst_node', 'burst_gap_ns', 'start_ns', 'seed'):
        integer(getattr(c, name), name)
    if c.src_node == c.dst_node:
        raise ValueError('src_node and dst_node must differ')
    if len(c.sizes) not in (1, c.jetties):
        raise ValueError('sizes must have one entry or one per Jetty')
    for size in c.sizes:
        integer(size, 'size', 1)
    if c.arrival not in ('batch', 'burst', 'poisson'):
        raise ValueError('unknown arrival pattern')
    if type(c.mean_gap_ns) not in (int,float) or not math.isfinite(c.mean_gap_ns) or not 0 < c.mean_gap_ns <= MAX_INT:
        raise ValueError('mean_gap_ns must be finite, positive and fit the ns range')
    rng = random.Random(c.seed)
    times = []
    for j in range(c.jetties):
        # Keep the absolute int64 origin exact; accumulate only relative gaps.
        elapsed_ns = 0.0
        jt = []
        for seq in range(c.wr_per_jetty):
            if c.arrival == 'poisson':
                elapsed_ns += rng.expovariate(1.0 / c.mean_gap_ns)
                if not math.isfinite(elapsed_ns):
                    raise ValueError('Poisson arrival exceeds supported ready_ns range')
                offset_ns = math.ceil(elapsed_ns)
                # Compare integers, not a rounded float representation of MAX_INT.
                if offset_ns > MAX_INT - c.start_ns:
                    raise ValueError('Poisson arrival exceeds supported ready_ns range')
                ready = c.start_ns + offset_ns
            else:
                ready = c.start_ns + (seq // c.burst_size * c.burst_gap_ns if c.arrival == 'burst' else 0)
            jt.append(ready)
        times.append(jt)
    pairs = []
    # Same eight-WR Jetty burst tie order as the published Nano-UB batch baseline.
    for base in range(0, c.wr_per_jetty, c.burst_size):
        for j in range(c.jetties):
            for seq in range(base, min(base + c.burst_size, c.wr_per_jetty)):
                size = c.sizes[0] if len(c.sizes) == 1 else c.sizes[j]
                pairs.append((make_wr(0, c.src_node, j+1, c.dst_node, size,
                                      times[j][seq], seq, 'synthetic'), None))
    rows, _ = canonicalize(pairs)
    validate(rows)
    return rows, {'schema_version': '1.0', 'generator': 'synthetic-v1',
                  'parameters': asdict(c), 'arrival_is_assumed': True,
                  'poisson_rounding': 'ceil absolute exponential-arrival time to integer ns',
                  'jetty_keys': [[c.src_node, j+1] for j in range(c.jetties)]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--jetties', type=int, default=3)
    p.add_argument('--wr-per-jetty', type=int, default=256)
    p.add_argument('--sizes', default='64,256,1024', help='one size, or one per Jetty; equal: --sizes 256')
    p.add_argument('--src-node', type=int, default=0)
    p.add_argument('--dst-node', type=int, default=1)
    p.add_argument('--arrival', choices=['batch', 'burst', 'poisson'], default='batch')
    p.add_argument('--burst-size', type=int, default=8)
    p.add_argument('--burst-gap-ns', type=int, default=1000)
    p.add_argument('--mean-gap-ns', type=float, default=100.)
    p.add_argument('--start-ns', type=int, default=0)
    p.add_argument('--seed', type=int, default=1)
    a = vars(p.parse_args()); output = Path(a.pop('output'))
    try:
        a['sizes'] = tuple(map(int, a['sizes'].split(',')))
        rows, metadata = generate(Config(**a))
        write_trace(output, rows)
        write_json(str(output)+'.meta.json', metadata)
        print(f'{len(rows)} WRs -> {output}')
    except (ValueError, OSError) as e:
        p.error(str(e))


if __name__ == '__main__':
    main()
