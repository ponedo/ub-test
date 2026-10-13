"""Validate WR Trace 1.0, map identities, run the actual SystemC backend."""
import argparse
import hashlib
import subprocess
from pathlib import Path
from workloads.schema.trace import read_trace, write_json

MAX_ROWS = 60000             # No TASSN/PSN wrap in this backend.
MAX_PAYLOAD = 16*1024*1024
MAX_TOTAL = 128*1024*1024
MAX_READY_NS = 1_000_000_000
MAX_JETTIES = 1024
FIELDS = ('wr_id','src_node','jetty_id','dst_node','mapped_src','mapped_jetty','mapped_dst',
          'mem_addr','payload_bytes','ready_ns','sequence','depends_on','phase')


def prepare(trace, output_dir, policy):
    if policy not in ('fifo','rr','drr'):
        raise ValueError('unsupported policy')
    rows=read_trace(trace)
    sources=sorted({r['src_node'] for r in rows})
    if len(sources)>1:
        raise ValueError('backend supports one source node only; multi-source trace rejected')
    if len(rows)>MAX_ROWS:
        raise ValueError('trace exceeds 60000 WR no-wrap limit')
    if any(r['payload_bytes']>MAX_PAYLOAD for r in rows):
        raise ValueError('WR exceeds 16 MiB payload limit')
    if sum(r['payload_bytes'] for r in rows)>MAX_TOTAL:
        raise ValueError('trace exceeds 128 MiB total payload limit')
    if any(r['ready_ns']>MAX_READY_NS for r in rows):
        raise ValueError('ready_ns exceeds supported 1-second injection horizon')
    jetties=sorted({r['jetty_id'] for r in rows})
    if len(jetties)>MAX_JETTIES:
        raise ValueError('more than 1024 active Jetties unsupported')
    destinations=sorted({r['dst_node'] for r in rows})
    nodes=sources+destinations
    node_map={node:i+1 for i,node in enumerate(nodes)}
    jetty_map={jetty:i+1 for i,jetty in enumerate(jetties)}
    offsets={dst:0 for dst in destinations}
    mapped=[]
    for row in rows:
        dst=row['dst_node'];addr=offsets[dst];offsets[dst]+=row['payload_bytes']
        mapped.append({**row,'mapped_src':node_map[row['src_node']],
                       'mapped_jetty':jetty_map[row['jetty_id']],'mapped_dst':node_map[dst],
                       'mem_addr':addr})
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    with (out/'input.tsv').open('w',encoding='utf-8',newline='') as f:
        f.write('nano-ub-adapter-v1\n'+'\t'.join(FIELDS)+'\n')
        for row in mapped:
            values={**row,'depends_on':';'.join(map(str,row['depends_on'])) or '-'}
            f.write('\t'.join(str(values[k]) for k in FIELDS)+'\n')
    manifest={'result_schema':'wr-results/1.0','trace_schema':'1.0','trace_sha256':hashlib.sha256(Path(trace).read_bytes()).hexdigest(),
              'backend':'nano-ub-systemc','semantics':'data-write','policy':policy,
              'source_nodes':sources,'nodes':node_map,'jetties':jetty_map,'destination_bytes':offsets,
              'wire_header_bytes':64,'ack_wire_bytes':64,'gbps':100,'propagation_ns':50,
              'scheduler_quantum_bytes':512,'scheduler_depth_per_jetty':4096,'source_fifo_depth':4096,'pipeline_fifo_depth':1,
              'max_wr_count':MAX_ROWS,'max_payload_bytes':MAX_PAYLOAD,'max_total_payload_bytes':MAX_TOTAL,
              'max_ready_ns':MAX_READY_NS,'phase_semantics':'opaque label, no implicit barrier',
              'dependency_semantics':'all specified prior WRs complete before submit; same-Jetty sequence cannot bypass',
              'destination_semantics':'identity and separate memory address spaces; one shared forward/reverse link and pooled RX/TP/memory service',
              'unsupported':['multiple source nodes','transport Fence/ODR/CQE controls','scatter-gather addresses','loss recovery','PSN/TASSN wrap'],
              'application_sidecars_consumed':False}
    write_json(out/'run.json',manifest)
    return out/'input.tsv'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace',required=True);p.add_argument('--output-dir',required=True)
    p.add_argument('--policy',choices=['fifo','rr','drr'],required=True)
    p.add_argument('--semantics',choices=['data-write'],required=True,
                   help='explicitly choose generic data WRITE; application sidecar protocol flags are outside this profile')
    p.add_argument('--binary',default='build-phase2/trace_e2e')
    a=p.parse_args()
    try:
        prepared=prepare(a.trace,a.output_dir,a.policy)
        subprocess.run([str(Path(a.binary).resolve()),a.policy,str(prepared.resolve()),str(Path(a.output_dir).resolve()/'systemc')],check=True)
    except (ValueError,OSError,subprocess.CalledProcessError) as e:p.error(str(e))


if __name__=='__main__':main()
