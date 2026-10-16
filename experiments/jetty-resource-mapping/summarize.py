#!/usr/bin/env python3
"""Snapshot saved attempt metadata into a NEW output directory; never run benchmarks."""
import argparse
import csv
import datetime
import html
import json
from pathlib import Path
from harness import HERE, sha


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def chart(path, rows, selected):
    panels = [('wall_seconds','Host wall time (s)','timing'),('cpu_seconds','Host user + system CPU (s)','timing'),
              ('peak_rss_mib','Peak RSS (MiB)','timing'),('layer_latency_ps','Simulated layer latency (ps)','timing'),
              ('tpn_query_calls','TPN query calls (instrumented)','instrumented'),('jetty_create_calls','Jetty create calls (instrumented)','instrumented'),
              ('tpn_records_scanned','TPN candidate records scanned (instrumented)','instrumented'),('remote_WQEs','Remote WQEs','timing')]
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1320" viewBox="0 0 1200 1320">',
         '<rect width="1200" height="1320" fill="white"/>','<g font-family="sans-serif" fill="#172554">',
         '<text x="35" y="34" font-size="23">PARTIAL measurements: completed selected runs only</text>',
         '<text x="35" y="59" font-size="14">A original (blue), B reverse index (orange), C (green). Missing values are not zero.</text>']
    colors={'A':'#2563eb','B':'#ea580c','C':'#15803d'}
    for i,(metric,title,phase) in enumerate(panels):
        left=80+(i%2)*590; top=120+(i//2)*290; width=450;height=190
        subset=[r for r in rows if r['phase']==phase and r['status']=='success' and r['assignments'] in selected and r.get(metric) is not None]
        maximum=max([r[metric] for r in subset]+[1])*1.12
        xmin,xmax=min(selected),max(selected)
        x=lambda n:left+(n-xmin)/(xmax-xmin or 1)*width
        y=lambda v:top+height-v/maximum*height
        svg.append(f'<text x="{left-45}" y="{top-20}" font-size="16">{html.escape(title)}</text>')
        for tick in range(5):
            value=maximum*tick/4; yy=y(value)
            svg += [f'<line x1="{left}" x2="{left+width}" y1="{yy}" y2="{yy}" stroke="#e2e8f0"/>',f'<text x="{left-8}" y="{yy+4}" text-anchor="end" font-size="11">{value:.3g}</text>']
        for n in sorted(selected):svg.append(f'<text x="{x(n)}" y="{top+height+20}" text-anchor="middle" font-size="12">{n/1000:g}K</text>')
        svg.append(f'<text x="{left+width/2}" y="{top+height+42}" text-anchor="middle" font-size="12">Assignments</text>')
        for arm,color in colors.items():
            points=sorted((r for r in subset if r['arm']==arm),key=lambda r:r['assignments'])
            # Every point is measured; lines only join adjacent selected sizes with evidence.
            for p,q in zip(points,points[1:]):
                if sorted(selected).index(q['assignments'])-sorted(selected).index(p['assignments'])==1:
                    svg.append(f'<line x1="{x(p["assignments"])}" y1="{y(p[metric])}" x2="{x(q["assignments"])}" y2="{y(q[metric])}" stroke="{color}" stroke-width="2"/>')
            for row in points:svg.append(f'<circle cx="{x(row["assignments"])}" cy="{y(row[metric])}" r="4" fill="{color}"><title>{arm}: {row[metric]}</title></circle>')
        if not subset:svg.append(f'<text x="{left+40}" y="{top+80}" font-size="15">No measured values</text>')
    svg += ['<text x="35" y="1280" font-size="13">Single trials; instrumented counters are separate runs. No C or missing-scale values inferred.</text>',
            '<text x="35" y="1303" font-size="13">Source: resources.csv and attempt.json / timing.tsv paths listed in summary.json.</text>','</g></svg>']
    path.write_text('\n'.join(svg)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--sizes',type=int,nargs='+',default=[5000,10000,20000,50000,100000],help='Completed sizes included in curves; full declared matrix still inventoried')
    a=p.parse_args()
    if a.out.exists():p.error('Output directory exists; use a new destination to preserve prior snapshots')
    matrix=json.loads((HERE/'matrix.yaml').read_text())['cases']
    records={}; provenance={}; rows=[]; timers=[]; parity=[]
    for path in sorted(a.raw.glob('*/attempt.json')):
        raw=path.read_bytes();r=json.loads(raw)
        records[r['attempt']]=r
        provenance[str(path)]={'sha256':__import__('hashlib').sha256(raw).hexdigest(),'status':r['status']}
    expected={row['case_id'] for row in matrix}
    for case_id in sorted(expected|records.keys()):
        r=records.get(case_id); parts=case_id.split('-')
        if not r and (len(parts)!=3 or not parts[0].isdigit()):continue
        n,arm,phase=(r['assignments'],r['arm'],r['phase']) if r else (int(parts[0]),parts[1],parts[2])
        row=dict(attempt=case_id,assignments=n,arm=arm,phase=phase,status=r['status'] if r else 'not_run',selected_size=n in a.sizes,source=str(a.raw/case_id/'attempt.json') if r else None)
        if r and r['status']=='success':
            res=r['stages']['ns3']; inv=r.get('logical_invariants',{})
            row.update(wall_seconds=res['wall_seconds'],user_cpu_seconds=res['user_cpu_seconds'],system_cpu_seconds=res['system_cpu_seconds'],cpu_seconds=res['user_cpu_seconds']+res['system_cpu_seconds'],peak_rss_mib=res['peak_rss_kib']/1024,strict_verify=r['stages']['verify']['status'],output_files=len(r['file_hashes']),remote_WQEs=inv.get('remote_WQEs'),target_TAs=inv.get('target_segments'))
            summary_path=a.raw/case_id/'run/summary.json';summary=json.loads(summary_path.read_text());provenance[str(summary_path)]={'sha256':sha(summary_path)}
            row['layer_latency_ps']=summary['layer_latency_ps']
            timing=a.raw/case_id/'timing.tsv'
            if phase=='instrumented' and timing.exists():
                provenance[str(timing)]={'sha256':sha(timing)}
                with timing.open() as f:tr=list(csv.DictReader(f,delimiter='\t'))
                mapped={v['name']:v for v in tr}
                for item in tr:timers.append(dict(attempt=case_id,assignments=n,arm=arm,**item))
                for key,name in [('tpn_query_calls','GetJettiesUsingTpn'),('tpn_records_scanned','TpnLookupJettyRecordsScanned'),('tpn_entries_compared','TpnLookupTransportEntriesCompared'),('tpn_live_vector_slots','TpnLookupLiveTransportVectorSlots'),('tpn_matched_jetties','TpnLookupMatchedJetties')]:
                    row[key]=int(mapped[name]['calls_or_count']) if name in mapped else None
                row['jetty_create_calls']=sum(int(mapped[name]['calls_or_count']) for name in ('CreateJettyBound','CreateJettyUnbound')) if all(name in mapped for name in ('CreateJettyBound','CreateJettyUnbound')) else None
                if 'GetJettiesUsingTpn' in mapped:row['tpn_query_thread_cpu_seconds']=int(mapped['GetJettiesUsingTpn']['inclusive_thread_cpu_ns'])/1e9
            if r.get('reference'):
                ref_id=Path(r['reference']).name;ref=records.get(ref_id)
                pr=dict(attempt=case_id,reference=ref_id,status='missing_reference')
                if ref and ref['status']=='success':
                    ah,bh=ref['file_hashes'],r['file_hashes'];different=sorted(k for k in ah.keys()|bh.keys() if ah.get(k)!=bh.get(k))
                    pr.update(status='compared_saved_sha256',files_reference=len(ah),files_attempt=len(bh),all_398_byte_identical=len(ah)==len(bh)==398 and not different,differing_files=';'.join(different),payload_bytes_identical=bool(ah.get('received-payloads.bin')) and ah.get('received-payloads.bin')==bh.get('received-payloads.bin'),events_including_time_identical=bool(ah.get('events.csv')) and ah.get('events.csv')==bh.get('events.csv'),summary_identical=bool(ah.get('summary.json')) and ah.get('summary.json')==bh.get('summary.json'),inputs_identical=ref['input_hashes']==r['input_hashes'],strict_verify=r['stages']['verify']['status'])
                parity.append(pr)
        rows.append(row)
    a.out.mkdir(parents=True)
    write_csv(a.out/'resources.csv',rows);write_csv(a.out/'counters-and-timers.csv',timers);write_csv(a.out/'parity.csv',parity)
    chart(a.out/'curves-partial.svg',rows,set(a.sizes))
    result=dict(partial=True,captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),raw=str(a.raw.resolve()),invocation=__import__('sys').argv,selected_sizes=a.sizes,attempts=rows,parity=parity,provenance=provenance,notes=['No benchmarks launched. Reads only saved small metadata and timing TSV files.','Byte parity uses recorded per-file SHA256 from completed guarded runs; raw payloads/events were not rehashed during this concurrent-safe summary.','C not run is missing evidence, not a zero-cost result.','Single-trial measurements are descriptive; no significance claim.','Jetty create calls measured only in instrumented runs; no resource count inferred from WQE count.','Curves include successful selected sizes only. Entire declared matrix, failures, and running attempts remain in CSV/JSON.'])
    (a.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    (a.out/'README.md').write_text('# PARTIAL measured snapshot\n\nGenerated: '+result['captured_utc']+'\n\nSelected curve scales: '+', '.join(map(str,a.sizes))+'. See resources.csv for all declared cases and explicit not_run/running/failed states.\n\n'+ '\n'.join('- '+n for n in result['notes'])+'\n\nArtifacts: resources.csv, counters-and-timers.csv, parity.csv, curves-partial.svg, summary.json. Exact invocation and source hashes are in summary.json. This snapshot never overwrites earlier evidence.\n')
    print(json.dumps({'output':str(a.out),'successful_selected_attempts':sum(r['status']=='success' and r['selected_size'] for r in rows),'declared_or_observed_rows':len(rows),'parity_comparisons':len(parity),'partial':True}))

if __name__=='__main__':main()
