#!/usr/bin/env python3
"""Export profiles without inherited credentials; preserve original measurements locally."""
import hashlib,json,os,re,shutil,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent;E=H/'evidence';RAW=Path('/workspace/prefill-cpu-raw');OUT=Path('/workspace/prefill-cpu-export');TOOLS=Path('/workspace/prefill-cpu-tools');PERF=TOOLS/'root/usr/bin/perf';ENV=os.environ|{'LD_LIBRARY_PATH':str(TOOLS/'root/usr/lib/x86_64-linux-gnu')}
values=list({v.encode() for k,v in os.environ.items() if re.search('SECRET|TOKEN|PASSWORD|ACCESS_KEY',k,re.I) and len(v)>=8})
def sha(data):return hashlib.sha256(data).hexdigest()
def scrub(data):
 count=0;fragments=0
 for value in values:
  n=data.count(value);count+=n;data=data.replace(value,b'*'*len(value))
  if len(value)<12:continue
  # Capture truncated prefix/suffix strings at an 8192-byte stack-dump boundary.
  for prefix in [True,False]:
   needle=value[:12] if prefix else value[-12:];start=0
   while (i:=data.find(needle,start))>=0:
    if prefix:
     length=12
     while length<len(value) and i+length<len(data) and data[i+length]==value[length]:length+=1
     left=i;right=i+length
    else:
     left=i;right=i+12;j=len(value)-12
     while left>0 and j>0 and data[left-1]==value[j-1]:left-=1;j-=1
    data=data[:left]+b'*'*(right-left)+data[right:];fragments+=1;start=right
 return data,count,fragments
def script_hash(path):
 r=subprocess.run([str(PERF),'script','-i',str(path)],env=ENV,capture_output=True,check=True);return sha(r.stdout)
if __name__=='__main__':
 assert not OUT.exists() or '--resume' in sys.argv,'preserve previous publication export; use --resume for owned export'
 (RAW/'probes').mkdir(exist_ok=True)
 for probe in E.glob('probe.data*'):
  if not (RAW/'probes'/probe.name).exists():shutil.copyfile(probe,RAW/'probes'/probe.name)
 if not OUT.exists():shutil.copytree(RAW,OUT,copy_function=os.link)
 changes=[]
 for original in sorted(RAW.rglob('*')):
  if not original.is_file():continue
  target=OUT/original.relative_to(RAW)
  if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);os.link(original,target)
  data=original.read_bytes();clean,count,fragments=scrub(data)
  if count or fragments:
   assert original.name in ['perf.data','probe.data','probe.data.old'],f'Unexpected sensitive bytes outside profile: {original}'
   before=script_hash(original);target.unlink();target.write_bytes(clean);assert sha(original.read_bytes())==sha(data);after=script_hash(target);assert before==after,'profile redaction changed decoded stacks'
   assert len(data)==len(clean)
   changes.append(dict(file=str(original.relative_to(RAW)),original_sha256=sha(data),published_sha256=sha(clean),full_value_occurrences=count,truncated_fragments=fragments,bytes_preserved=len(data),decoded_stack_sha256=before,decoded_stack_byte_parity=True))
  else:assert target.read_bytes()==data
 for probe in (OUT/'probes').glob('probe.data*'):shutil.copyfile(probe,E/probe.name)
 # Audit all exported/public files for complete known credential values.
 for root in [OUT,E]:
  for p in root.rglob('*'):
   if p.is_file():
    b=p.read_bytes();assert not any(v in b for v in values),f'credential bytes remain: {p}'
 report=dict(original_raw_root=str(RAW),published_export_root=str(OUT),scope='Equal-length redaction of inherited credential strings in raw DWARF stack bytes only. Original raw profiles remain local and are not published. All other raw files are byte-identical. Decoded perf script output is byte-identical before/after for every redacted profile.',known_credential_values_audited=len(values),changes=changes)
 (E/'publication-redactions.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Publication export verified;',len(changes),'profiles redacted; decoded stacks byte-identical; other raw files unchanged')
