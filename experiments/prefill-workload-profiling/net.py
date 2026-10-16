"""Unauthenticated official downloads and content-addressed HTTP range cache."""
import hashlib,io,json,time,urllib.request,urllib.error
from pathlib import Path

class Fetcher:
 def __init__(self,cache):self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True);self.records={}
 def request(self,url,headers=None):
  for attempt in range(4):
   try:
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ub-prefill-profiler/1.0',**(headers or {})}),timeout=90)
   except urllib.error.HTTPError as e:
    if e.code not in [429,500,502,503,504] or attempt==3:raise
   except (TimeoutError,OSError):
    if attempt==3:raise
   time.sleep(2**attempt)
 def full(self,url):
  key=hashlib.sha256(url.encode()).hexdigest();dest=self.cache/'files'/key;dest.parent.mkdir(exist_ok=True)
  if not dest.exists():
   tmp=dest.with_suffix('.partial')
   with self.request(url) as r,tmp.open('wb') as f:
    while data:=r.read(1024*1024):f.write(data)
   tmp.replace(dest)
  h=hashlib.sha256(dest.read_bytes()).hexdigest();self.records[url]=dict(url=url,bytes=dest.stat().st_size,sha256=h,access='full')
  return dest
 def json(self,url):return json.loads(self.full(url).read_text())
 def range(self,url,start,end):
  tag=f'{start}-{end}';key=hashlib.sha256(url.encode()).hexdigest();directory=self.cache/'ranges'/key;directory.mkdir(parents=True,exist_ok=True)
  dest=directory/tag;meta=directory/(tag+'.json')
  if not dest.exists():
   spec=f'bytes={start}-{end}' if start>=0 else f'bytes={start}'
   with self.request(url,{'Range':spec}) as r:
    cr=r.headers.get('Content-Range','');data=r.read()
    if r.status!=206 or not cr.startswith('bytes '):raise RuntimeError('range unsupported '+url)
    bounds,total=cr[6:].split('/');lo,hi=map(int,bounds.split('-'))
    if len(data)!=hi-lo+1 or (start>=0 and (lo!=start or hi!=end)):raise RuntimeError('incorrect returned range')
    info=dict(start=lo,end=hi,size=int(total),etag=r.headers.get('ETag'),sha256=hashlib.sha256(data).hexdigest())
   dest.write_bytes(data);meta.write_text(json.dumps(info))
  info=json.loads(meta.read_text());record=self.records.setdefault(url,dict(url=url,access='projected-parquet-ranges',size=info['size'],etag=info['etag'],ranges={}))
  if record['etag']!=info['etag'] or record['size']!=info['size']:raise RuntimeError('remote object changed')
  record['ranges'][tag]=info
  return dest.read_bytes(),info

class RemoteParquet(io.RawIOBase):
 def __init__(self,fetch,url):
  super().__init__();self.fetch=fetch;self.url=url;self.pos=0
  _,meta=fetch.range(url,-8,'');self.size=meta['size']
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.pos
 def seek(self,offset,whence=0):
  pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
  if pos<0:raise ValueError('negative seek')
  self.pos=pos;return pos
 def read(self,size=-1):
  if size<0:size=self.size-self.pos
  size=min(size,self.size-self.pos)
  if size<=0:return b''
  data,_=self.fetch.range(self.url,self.pos,self.pos+size-1);self.pos+=size;return data
