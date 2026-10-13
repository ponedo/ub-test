"""Read-only audit of saved compressed events; never invokes SystemC or generators."""
import argparse
import json
import lzma
import shutil
import tempfile
from pathlib import Path
from evaluation.analyze import analyze,common_backlogged_window
from experiments.ingress.run import digest,inspect_run


def canonical(value):return json.dumps(json.loads(json.dumps(value)),sort_keys=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',nargs='?',default='experiments/ingress/output');a=p.parse_args();root=Path(a.output)
    saved=json.loads((root/'summary.json').read_text());manifest=json.loads((root/'raw_events_manifest.json').read_text())
    records={r['path']:r for r in manifest}
    with tempfile.TemporaryDirectory() as temporary:
        directories=[]
        for i,r in enumerate(saved):
            relative=Path(r['scenario'])/r['permutation']/r['mode']/r['policy'];source=root/relative;dest=Path(temporary)/str(i);dest.mkdir();directories.append(dest)
            for name in ('systemc.wr.csv','run.json'):shutil.copyfile(source/name,dest/name)
            for name in ('systemc.events.csv','systemc.timeline.csv'):
                path=source/(name+'.xz');record=records[str(relative/(name+'.xz'))]
                assert digest(path)==record['compressed_sha256']
                with lzma.open(path,'rb') as src,(dest/name).open('wb') as dst:shutil.copyfileobj(src,dst)
                assert digest(dest/name)==record['uncompressed_sha256']
        window=common_backlogged_window(directories)
        assert (list(window) if window else None)==json.loads((root/'window.json').read_text())['primary_window_ns']
        for i,(r,d) in enumerate(zip(saved,directories)):
            actual=analyze(d,*(window or (0,1)))
            for key in actual:
                if key=='fairness':
                    for field in ['window_ns','wire_bytes','payload_bytes','wire_jain','payload_jain','minimum_scheduler_queue','valid_all_jetties_backlogged']:
                        assert canonical(actual[key][field])==canonical(r[key][field]),(i,key,field)
                else:assert canonical(actual[key])==canonical(r[key]),(i,key)
            info,wr=inspect_run(d,r['mode']);assert canonical(info)==canonical(r['timeline'])
            source=root/r['scenario']/r['permutation']/r['mode']/r['policy'];assert (d/'orders.csv').read_bytes()==(source/'orders.csv').read_bytes()
            for j,v in r['full_run']['wire_bytes'].items():assert v==sum(x['payload_bytes']+64 for x in wr.values() if x['jetty_id']==int(j))
            for j,v in r['full_run']['payload_bytes'].items():assert v==sum(x['payload_bytes'] for x in wr.values() if x['jetty_id']==int(j))
            print('PASS audit',i+1,'/',len(saved),r['scenario'],r['permutation'],r['mode'],r['policy'],flush=True)
    print('PASS: raw hashes, common window, all latency/throughput/queue/fairness metrics, PSN/ACK causality, FIFO and epoch invariants')
if __name__=='__main__':main()
