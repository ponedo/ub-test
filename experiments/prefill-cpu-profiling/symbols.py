#!/usr/bin/env python3
import hashlib,json,re,shutil,subprocess
from pathlib import Path
out=Path('/workspace/prefill-cpu-raw/symbols');out.mkdir(exist_ok=True);manifest={}
for variant,root in [('original',Path('/workspace/ns-3-ub')),('timed',Path('/workspace/prefill-cpu-native'))]:
 exe=root/'build/scratch/ns3.44-multi-npu-relay';ldd=subprocess.check_output(['ldd',str(exe)],text=True)
 paths=[exe]+[Path(s) for s in re.findall(r'(?:=> )?(/[^ \n]+)',ldd)]
 for p in paths:
  dest=out/variant/p.relative_to('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);manifest[str(dest.relative_to(out))]=hashlib.sha256(dest.read_bytes()).hexdigest()
(out/'sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
(out/'README.md').write_text('Original and timed executable plus every ldd-resolved ELF dependency, following symlinks. Absolute origin paths are retained below original/ and timed/. Use perf buildid-cache --add EXTRACTED_ELF to resolve archived perf.data on another machine. Compile flags and ELF/build IDs are separately in evidence/build-*.\n')
