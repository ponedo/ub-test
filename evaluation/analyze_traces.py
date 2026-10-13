"""Analyze WR demand distributions; these are NOT SystemC performance results."""
import argparse
import collections
import csv
import json
from pathlib import Path
from workloads.schema.trace import read_trace, write_json


def analyze(path):
    path=Path(path)
    rows=read_trace(path)
    metadata=json.loads(Path(str(path)+'.meta.json').read_text()) if Path(str(path)+'.meta.json').exists() else {}
    wrs=[json.loads(line) for line in Path(str(path)+'.moe.jsonl').read_text().splitlines()] if Path(str(path)+'.moe.jsonl').exists() else []
    by_id={r['wr_id']:r for r in rows}
    if Path(str(path)+'.moe.jsonl').exists():
        if len(wrs)!=len(rows) or {m['wr_id'] for m in wrs}!=set(by_id):
            raise ValueError('MoE sidecar WR identity mismatch')
        for m in wrs:
            r=by_id[m['wr_id']]
            n=m['sge_pair_count']
            if type(n) is not int or not 1<=n<=6 or m['sge_count']!=2*n or len(m['sge_lengths'])!=2*n or len(m['tokens'])!=n:
                raise ValueError('MoE sidecar SGE structure mismatch')
            if any(type(x) is not int or x<=0 for x in m['sge_lengths']):
                raise ValueError('MoE sidecar invalid SGE length')
            if any(m[k]!=r[k] for k in ('src_node','jetty_id','dst_node')):
                raise ValueError('MoE sidecar endpoint mismatch')
            if sum(m['sge_lengths'])!=r['payload_bytes'] or m['semantic_bytes']+m['padding_bytes']!=r['payload_bytes']:
                raise ValueError('MoE sidecar byte conservation mismatch')
    histogram=collections.Counter(r['payload_bytes'] for r in rows)
    aggregation=collections.Counter(m['sge_pair_count'] for m in wrs)
    jetty_keys=sorted(set(tuple(k) for k in metadata.get('jetty_keys',[])) | {(r['src_node'],r['jetty_id']) for r in rows})
    jetties=[]
    for src,jetty in jetty_keys:
        group=[r for r in rows if (r['src_node'],r['jetty_id'])==(src,jetty)]
        ids={r['wr_id'] for r in group}
        mgroup=[m for m in wrs if m['wr_id'] in ids]
        jetties.append({'case':path.stem,'src_node':src,'jetty_id':jetty,'wr_count':len(group),
                        'payload_bytes':sum(r['payload_bytes'] for r in group),
                        'full_wr_count':sum(m['sge_pair_count']==6 for m in mgroup),
                        'full_wr_fraction':sum(m['sge_pair_count']==6 for m in mgroup)/len(mgroup) if mgroup else None,
                        'mean_payload_bytes':sum(r['payload_bytes'] for r in group)/len(group) if group else None,
                        'mean_pairs':sum(m['sge_pair_count'] for m in mgroup)/len(mgroup) if mgroup else None})
    full=aggregation[6]
    total_pairs=sum(n*count for n,count in aggregation.items())
    dominant=max(histogram.values(),default=0)
    summary={'case':path.stem,'wr_count':len(rows),'active_jetties':sum(x['wr_count']>0 for x in jetties),
             'configured_jetties':len(jetty_keys),'payload_bytes':sum(r['payload_bytes'] for r in rows),
             'distinct_wr_sizes':len(histogram),'dominant_size_fraction':dominant/len(rows) if rows else None,
             'full_wr_fraction':full/len(wrs) if wrs else None,
             'mean_pairs':total_pairs/len(wrs) if wrs else None,
             'pair_slot_utilization':total_pairs/(6*len(wrs)) if wrs else None,
             'min_ready_ns':min((r['ready_ns'] for r in rows),default=None),
             'max_ready_ns':max((r['ready_ns'] for r in rows),default=None)}
    return summary,jetties,histogram,aggregation


def write_csv(path,rows,fields=None):
    with Path(path).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--traces',nargs='+',required=True)
    p.add_argument('--output-dir',required=True)
    a=p.parse_args();out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    summaries=[];jetties=[];hist=[];agg=[];jetty_hist=[];destinations=[]
    for path in a.traces:
        s,j,h,g=analyze(path);summaries.append(s);jetties.extend(j)
        rows=read_trace(path)
        counts=collections.Counter((r['src_node'],r['jetty_id'],r['payload_bytes']) for r in rows)
        jetty_hist.extend(dict(case=s['case'],src_node=src,jetty_id=jetty,payload_bytes=size,wr_count=count)
                          for (src,jetty,size),count in sorted(counts.items()))
        for src,dst in sorted({(r['src_node'],r['dst_node']) for r in rows}):
            group=[r for r in rows if (r['src_node'],r['dst_node'])==(src,dst)]
            destinations.append(dict(case=s['case'],src_node=src,dst_node=dst,wr_count=len(group),
                                     payload_bytes=sum(r['payload_bytes'] for r in group)))
        hist.extend(dict(case=s['case'],payload_bytes=size,wr_count=count) for size,count in sorted(h.items()))
        agg.extend(dict(case=s['case'],sge_pairs=n,wr_count=g[n]) for n in range(1,7))
    write_csv(out/'summary.csv',summaries);write_csv(out/'jetties.csv',jetties)
    write_csv(out/'histograms.csv',hist,('case','payload_bytes','wr_count'))
    write_csv(out/'aggregation.csv',agg)
    write_csv(out/'jetty_histograms.csv',jetty_hist,('case','src_node','jetty_id','payload_bytes','wr_count'))
    write_csv(out/'destinations.csv',destinations,('case','src_node','dst_node','wr_count','payload_bytes'))
    write_json(out/'summary.json',{'metric_scope':'generated offered demand only, not simulation performance','cases':summaries})
    for s in summaries:print(json.dumps(s,sort_keys=True))


if __name__=='__main__':main()
