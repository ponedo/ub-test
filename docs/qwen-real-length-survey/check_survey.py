"""Consistency checks on metadata; never downloads or verifies remote trace content."""
import csv, hashlib, json
from pathlib import Path
P=Path(__file__).parent
m=json.loads((P/'inventory.json').read_text())
assert m['revision']=='27febb7b2d24169560a9f6f83d38eb53f94916cf'
assert m['content_requests']==m['content_downloaded_bytes']==0
assert len(m['children'])==5
assert all(c['complete'] and c['next_page'] is None for c in m['coverage'])
assert len(m['pages'])+7<=80
assert len({r['path'] for r in m['entries']})==len(m['entries'])
for page in m['pages']:
    cache=P/'metadata-pages'/(hashlib.sha256(page['url'].encode()).hexdigest()+'.json')
    saved=json.loads(cache.read_text());body=saved['body'].encode()
    assert saved['url']==page['url']
    assert hashlib.sha256(body).hexdigest()==page['sha256']
    assert len(body)==page['bytes'] and len(json.loads(body))==page['entries']
for c in m['coverage']:
    rows=[r for r in m['entries'] if r['path'].startswith(c['path']+'/')]
    if c['path'].rsplit('/',1)[-1] not in ('mmlu','mmlu_ZH_CN'):continue
    files=[r for r in rows if r['type']=='file']
    assert len(rows)==c['entries'] and len(files)==c['files']
    assert sum(r['size'] for r in files)==c['file_bytes']
with (P/'candidate-shortlist.csv').open() as f:
    candidates=list(csv.DictReader(f))
assert len(candidates)==2 and len({r['path'] for r in candidates})==2
assert sum(int(r['bytes']) for r in candidates)==16138889
assert [int(r['prefill_N']) for r in candidates]==[224,393]
assert all(r['path'].endswith('.json') for r in candidates)
for name in ('expansion-candidates.csv','bounded-batch-candidates.csv'):
    with (P/name).open() as f: candidates.extend(csv.DictReader(f))
assert len(candidates)==7 and len({r['path'] for r in candidates})==7
assert sum(int(r['bytes']) for r in candidates)==93704335
assert [int(r['prefill_N']) for r in candidates]==[224,393,924,832,691,597,592]
assert all(r['download_status']=='DOWNLOADED_PRIVATELY_AND_DOUBLE_VALIDATED' for r in candidates)
with (P/'actual-sample-lengths.csv').open() as f: actual=list(csv.DictReader(f))
assert [int(r['tokens_per_layer']) for r in actual]==[22,224,393,924,832,691,597,592]
assert sum(int(r['tokens_per_layer']) for r in actual)==4275
assert len({r['sha256'] for r in actual})==8
with (P/'length-availability.csv').open() as f: availability=list(csv.DictReader(f))
assert [int(r['target_tokens']) for r in availability]==[256,512,1024,2048,4096]
assert all(r['dataset_wide_absence_claim'].startswith('NONE') for r in availability)
print('PASS: public metadata hashes/counts/coverage, three-stage bounded selection, eight actual samples and qualified length targets')
