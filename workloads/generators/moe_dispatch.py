"""CPU, uncached DeepEP-Ascend-derived DATA WRs; no NPU/simulator dependency."""
import argparse
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from workloads.schema.trace import canonicalize, integer, make_wr, validate, write_json, write_trace

SOURCE_COMMIT = '3b25377d04b24fc6154698ded78a2bcb2c59afff'
SGE_PAIRS = 6
ALIGN = 32
SQ_WQEBBS = 32768


def align(n):
    return (n + ALIGN - 1) // ALIGN * ALIGN


@dataclass(frozen=True)
class Config:
    tokens: int = 128                # Actual tokens per included source rank.
    capacity: int = 128              # Compiled maximum, not automatically actual tokens.
    hidden_size: int = 1024          # Elements, not bytes.
    dtype: str = 'bf16'
    sf_packs: int = 0                # Explicit int16 packs, never guessed from hidden size.
    top_k: int = 4
    experts: int = 64
    ranks: int = 8
    aivs: int = 16
    src_nodes: tuple = (0,)
    score_factor: float = 1.0        # Hot-rank score multiplier, NOT traffic ratio.
    hot_rank: int = 0
    seed: int = 1
    start_ns: int = 0
    aiv_stagger_ns: int = 0
    token_prep_ns: int = 0


def check_config(c):
    for name in ('tokens', 'sf_packs', 'hot_rank', 'seed', 'start_ns', 'aiv_stagger_ns', 'token_prep_ns'):
        integer(getattr(c, name), name)
    for name in ('capacity', 'hidden_size', 'top_k', 'experts', 'ranks', 'aivs'):
        integer(getattr(c, name), name, 1)
    if c.tokens > c.capacity:
        raise ValueError('actual tokens exceed compiled capacity')
    if c.ranks < 2 or c.ranks > 256 or c.ranks % 2:
        raise ValueError('profile supports even rank counts 2..256')
    if not 16 <= c.aivs <= 64:
        raise ValueError('public host wrapper/profile requires 16..64 AIVs')
    if c.experts > 512 or c.experts % c.ranks:
        raise ValueError('experts must be divisible by ranks and <=512 (dispatch SIMT threads)')
    if c.top_k > min(32, c.experts):
        raise ValueError('top_k exceeds expert count or warp bound 32')
    if c.hot_rank >= c.ranks or not math.isfinite(c.score_factor) or c.score_factor < 1:
        raise ValueError('hot_rank out of range or invalid score_factor (must be finite >=1)')
    if c.dtype not in ('bf16', 'fp8') or (c.dtype == 'bf16' and c.sf_packs != 0) or (c.dtype == 'fp8' and c.sf_packs == 0):
        raise ValueError('bf16 needs zero SF packs; fp8 needs an explicit positive SF pack count')
    if c.hidden_size * (2 if c.dtype == 'bf16' else 1) % ALIGN:
        raise ValueError('profile requires hidden data length aligned to 32 B')
    if not c.src_nodes or len(set(c.src_nodes)) != len(c.src_nodes):
        raise ValueError('nonempty, distinct src_nodes required')
    for src in c.src_nodes:
        integer(src, 'src_node')
        if src >= c.ranks:
            raise ValueError('source rank out of range')
    if c.capacity * c.ranks >= 2**24:
        raise ValueError('source reduction-count bound exceeded')
    cap = (c.capacity+c.aivs-1)//c.aivs
    entries = cap * min(c.top_k, c.ranks-1)
    max_sqes = min(entries, (c.ranks-1)*((cap+5)//6), (entries+(c.ranks-1)*5)//6)
    if max_sqes*4 > SQ_WQEBBS:
        raise ValueError('compiled worst-case SQ capacity exceeded; no silent flush/rechunk')


def token_layout(c):
    hidden = c.hidden_size * (2 if c.dtype == 'bf16' else 1)
    scales = c.sf_packs * 2
    # Uncached TokenLayout: aligned int64 top-k indices, float weights, int32 token ID.
    metadata_raw_with_index_padding = align(8*c.top_k) + 4*c.top_k + 4
    metadata = align(scales) + align(metadata_raw_with_index_padding)
    semantic = hidden + scales + 8*c.top_k + 4*c.top_k + 4
    return {'hidden_bytes': hidden, 'metadata_sge_bytes': metadata,
            'scale_bytes': scales, 'semantic_bytes': semantic,
            'transfer_bytes': hidden+metadata, 'padding_bytes': hidden+metadata-semantic}


def generate(c, routes_override=None):
    check_config(c)
    layout = token_layout(c)
    rng = random.Random(c.seed)
    per_aiv = (c.capacity+c.aivs-1)//c.aivs
    experts_per_rank = c.experts//c.ranks
    pairs, routes, ownership = [], [], []
    stats = dict(token_expert_assignments=0, token_rank_pairs=0, local_token_rank_pairs=0,
                 remote_token_rank_pairs=0, local_transfer_bytes=0, remote_transfer_bytes=0)
    for src in sorted(c.src_nodes):
        buckets = {(aiv, dst): [] for aiv in range(c.aivs) for dst in range(c.ranks) if dst != src}
        for token in range(c.tokens):
            if routes_override is None:
                # gate.py's factor-score concept, but Python double RNG, not NPU torch RNG.
                scores = [rng.random()*(c.score_factor if expert//experts_per_rank == c.hot_rank else 1.)
                          for expert in range(c.experts)]
                chosen = sorted(range(c.experts), key=lambda e: (-scores[e], e))[:c.top_k]
            else:
                try:
                    chosen = list(routes_override[src][token])
                except (KeyError, IndexError, TypeError) as e:
                    raise ValueError('incomplete route fixture') from e
            if len(chosen) != c.top_k or len(set(chosen)) != c.top_k or any(type(e) is not int or not 0 <= e < c.experts for e in chosen):
                raise ValueError('each token must select top_k distinct valid experts')
            aiv = token // per_aiv
            destinations = sorted({e//experts_per_rank for e in chosen})
            routes.append({'src_node': src, 'token': token, 'aiv': aiv,
                           'experts': chosen, 'destination_ranks': destinations})
            stats['token_expert_assignments'] += len(chosen)
            stats['token_rank_pairs'] += len(destinations)
            for dst in destinations:
                if dst == src:
                    stats['local_token_rank_pairs'] += 1
                    stats['local_transfer_bytes'] += layout['transfer_bytes']
                else:
                    buckets[aiv, dst].append(token)
                    stats['remote_token_rank_pairs'] += 1
                    stats['remote_transfer_bytes'] += layout['transfer_bytes']
        for aiv in range(c.aivs):
            begin = min(c.tokens, aiv*per_aiv)
            end = min(c.tokens, (aiv+1)*per_aiv)
            ready = c.start_ns + aiv*c.aiv_stagger_ns + (end-begin)*c.token_prep_ns
            seq = 0
            first = len(pairs)
            # One deterministic realization of nondeterministic atomic reservations.
            # Destination blocks in cyclic rank order; ascending token within each block.
            for shift in range(1, c.ranks):
                dst = (src+shift)%c.ranks
                tokens = buckets[aiv, dst]
                for offset in range(0, len(tokens), SGE_PAIRS):
                    group = tokens[offset:offset+SGE_PAIRS]
                    n = len(group)
                    row = make_wr(0, src, aiv, dst, n*layout['transfer_bytes'], ready, seq, 'dispatch_data')
                    metadata = {'src_node': src, 'jetty_id': aiv, 'dst_node': dst,
                                'tokens': group, 'sge_pair_count': n, 'sge_count': 2*n,
                                'sge_lengths': [v for _ in group for v in (layout['hidden_bytes'],layout['metadata_sge_bytes'])],
                                'semantic_bytes': n*layout['semantic_bytes'],
                                'padding_bytes': n*layout['padding_bytes'],
                                'aggregation_end': 'full' if n==6 else 'destination_tail',
                                'sqe_descriptor_bytes': 48+32*n, 'reserved_wqebb_bytes': 256,
                                'final_sqe_fence_and_cqe': False}
                    pairs.append((row, metadata)); seq += 1
            if seq:
                pairs[-1][1]['final_sqe_fence_and_cqe'] = True
            ownership.append({'src_node':src, 'jetty_id':aiv, 'token_begin':begin, 'token_end':end,
                              'wr_count':seq, 'assumed_doorbell_ready_ns':ready,
                              'payload_bytes':sum(row['payload_bytes'] for row,_ in pairs[first:])})
    rows, wr_metadata = canonicalize(pairs)
    checked = validate(rows)
    if checked['payload_bytes'] != stats['remote_transfer_bytes']:
        raise ValueError('internal byte conservation failure')
    if sum(m['sge_pair_count'] for m in wr_metadata) != stats['remote_token_rank_pairs']:
        raise ValueError('internal token-rank conservation failure')
    metadata = {'schema_version':'1.0', 'generator':'moe-dispatch-v1',
                'source_commit':SOURCE_COMMIT, 'parameters':asdict(c), 'token_layout':layout,
                'conservation':stats, 'jetties':ownership,
                'jetty_keys':[[src,aiv] for src in sorted(c.src_nodes) for aiv in range(c.aivs)],
                'arrival_is_assumed':True,
                'arrival_formula':'start_ns + aiv*aiv_stagger_ns + owned_tokens*token_prep_ns; one batch per AIV',
                'scope':'uncached remote payload WRITE only; local copies/control stores/NOPs excluded',
                'order_model':'cyclic peer blocks, ascending tokens; deterministic atomic-order approximation',
                'final_sqe_flags':'sidecar records fence/CQE; generic trace does not claim to encode transport ODR/fence'}
    return rows, metadata, wr_metadata, routes


def save(output, result):
    rows, metadata, wr_metadata, routes = result
    output = Path(output)
    write_trace(output, rows)
    write_json(str(output)+'.meta.json', metadata)
    for suffix, entries in ('.moe.jsonl', wr_metadata), ('.routes.jsonl', routes):
        import json
        with Path(str(output)+suffix).open('w',encoding='utf-8') as f:
            for entry in entries:
                f.write(json.dumps(entry,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True)
    for name,default in [('tokens',128),('capacity',None),('hidden-size',1024),('sf-packs',0),
                         ('top-k',4),('experts',64),('ranks',8),('aivs',16),('hot-rank',0),
                         ('seed',1),('start-ns',0),('aiv-stagger-ns',0),('token-prep-ns',0)]:
        p.add_argument('--'+name,type=int,default=default)
    p.add_argument('--dtype',choices=['bf16','fp8'],default='bf16')
    p.add_argument('--src-nodes',default='0',help='comma-separated ranks or all')
    p.add_argument('--score-factor',type=float,default=1.)
    a=vars(p.parse_args()); output=a.pop('output')
    try:
        a['capacity']=max(1,a['tokens']) if a['capacity'] is None else a['capacity']
        a['src_nodes']=tuple(range(a['ranks'])) if a['src_nodes']=='all' else tuple(map(int,a['src_nodes'].split(',')))
        result=generate(Config(**a)); save(output,result)
        print(f'{len(result[0])} remote WRs -> {output}')
    except (ValueError,OSError) as e:
        p.error(str(e))


if __name__ == '__main__':
    main()
