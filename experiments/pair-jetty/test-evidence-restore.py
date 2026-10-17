#!/usr/bin/env python3
"""Small negative tests for the evidence transport reader (no simulation)."""
import copy,hashlib,json,pathlib,subprocess,sys,tempfile
script=pathlib.Path(__file__).with_name('restore-evidence.py').resolve();results=[]
with tempfile.TemporaryDirectory() as tmp:
 root=pathlib.Path(tmp)
 base={'format':'pair-jetty-cas-v1','chunk_bytes':8*1024*1024,'files':{'ok.txt':{'bytes':0,'sha256':hashlib.sha256(b'').hexdigest(),'chunks':[]}},'objects':{},'bundles':[]}
 for name,mutate in [('valid',lambda m:m),('parent_path',lambda m:m['files'].update({'../escape':m['files'].pop('ok.txt')})),('absolute_path',lambda m:m['files'].update({'/escape':m['files'].pop('ok.txt')})),('bad_chunk_limit',lambda m:m.update(chunk_bytes=1000000000)),('wrong_file_hash',lambda m:m['files']['ok.txt'].update(sha256='0'*64))]:
  d=root/name;d.mkdir();m=copy.deepcopy(base);mutate(m);(d/'manifest.json').write_text(json.dumps(m));r=subprocess.run([sys.executable,str(script),'--bundle-dir',str(d),'--out',str(d/'out')],capture_output=True,text=True)
  assert (r.returncode==0)==(name=='valid'),(name,r.stdout,r.stderr);results.append({'case':name,'expected_rejection':name!='valid','returncode':r.returncode,'status':'PASS'})
 d=root/'valid';r=subprocess.run([sys.executable,str(script),'--bundle-dir',str(d),'--out',str(d/'out')],capture_output=True,text=True);assert r.returncode;results.append({'case':'nonempty_output','status':'PASS'})
 d=root/'symlink';d.mkdir();(d/'manifest.json').write_text(json.dumps(base));(d/'target').mkdir();(d/'out').symlink_to(d/'target');r=subprocess.run([sys.executable,str(script),'--bundle-dir',str(d),'--out',str(d/'out')],capture_output=True,text=True);assert r.returncode;results.append({'case':'symlink_output','status':'PASS'})
print(json.dumps({'status':'PASS','tests':results},indent=2))
