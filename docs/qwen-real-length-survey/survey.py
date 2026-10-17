"""Public tree metadata ONLY. Never requests resolve/raw content or credentials."""
import csv, hashlib, json, re, shutil, urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime, timezone
DATASET='core12345/MoE_expert_selection_trace'
REV='27febb7b2d24169560a9f6f83d38eb53f94916cf'
ROOT='Qwen/Qwen3-235B-A22B-FP8'
BASE=f'https://huggingface.co/api/datasets/{DATASET}/tree/{REV}/'
OUT=Path(__file__).parent
PAGE_CAP=30
TOTAL_CAP=80
PRIOR_COMPLETED_PAGES=7
pages=[]
CACHE=OUT/'metadata-pages'
CACHE.mkdir(exist_ok=True)
def inventory(path,recursive):
    url=BASE+urllib.parse.quote(path,safe='/')+f'?recursive={str(recursive).lower()}&limit=1000'
    entries=[]; count=0
    while url and count<PAGE_CAP and len(pages)+PRIOR_COMPLETED_PAGES<TOTAL_CAP:
        if not url.startswith(BASE): raise ValueError('Unexpected pagination destination')
        if shutil.disk_usage(OUT).free < 8*1024**3: raise RuntimeError('8 GiB free-disk guard')
        cache=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.json')
        if cache.exists():
            saved=json.loads(cache.read_text()); data=saved['body'].encode(); link=saved['link']
        else:
            with urllib.request.urlopen(url,timeout=60) as r:
                data=r.read(4*1024*1024+1)
                if len(data)>4*1024*1024: raise RuntimeError('Metadata page exceeds 4 MiB')
                link=r.headers.get('Link','')
            cache.write_text(json.dumps({'url':url,'body':data.decode(),'link':link}))
        rows=json.loads(data)
        pages.append({'url':url,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'entries':len(rows)})
        entries.extend(rows); count+=1
        match=re.search(r'<([^>]+)>;\s*rel="next"',link)
        url=match.group(1) if match else None
    paths=[e['path'] for e in entries]
    if len(paths)!=len(set(paths)): raise ValueError('Duplicate paths across pages')
    return entries,{'path':path,'pages':count,'entries':len(entries),'complete':url is None,'next_page':url}
def main():
    checkpoint=json.loads((OUT/'prior-observations.json').read_text())
    children=checkpoint['children']; rootcoverage=checkpoint['coverage'][0]
    allrows=[]; cover=checkpoint['coverage'][:]
    for child in children:
        if child['type']!='directory' or child['path'] in {c['path'] for c in cover}: continue
        rows,c=inventory(child['path'],True); allrows.extend(rows)
        files=[r for r in rows if r['type']=='file']; sizes=sorted(r['size'] for r in files)
        c.update(files=len(files),directories=len(rows)-len(files),file_bytes=sum(sizes),min_bytes=min(sizes) if sizes else None,max_bytes=max(sizes) if sizes else None)
        cover.append(c); print(json.dumps(c),flush=True)
    result={'dataset':DATASET,'revision':REV,'root':ROOT,'observed_at_utc':datetime.now(timezone.utc).isoformat(),'page_cap_per_inventory':PAGE_CAP,'total_page_cap':TOTAL_CAP,'prior_completed_pages':PRIOR_COMPLETED_PAGES,'prior_observations': 'prior-observations.json; prior complete inventories have summary-only retention after process interruption', 'content_requests':0,'content_downloaded_bytes':0,'children':children,'coverage':cover,'pages':pages,'entries':allrows}
    (OUT/'inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'directory-coverage.csv').open('w',newline='') as f:
        fields=['path','pages','entries','complete','files','directories','file_bytes','min_bytes','max_bytes','next_page']; w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader();w.writerows(cover)
if __name__=='__main__': main()
