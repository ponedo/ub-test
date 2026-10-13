"""Read-only verification of an explicitly supplied DeepEP-Ascend checkout."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('checkout');a=p.parse_args()
    root=Path(__file__).resolve().parents[2]
    manifest=json.loads((root/'docs/phase1/source_manifest.json').read_text())
    commit=subprocess.check_output(['git','-C',a.checkout,'rev-parse','HEAD'],text=True).strip()
    if commit!=manifest['commit']:raise SystemExit('source commit mismatch')
    for item in manifest['files']:
        actual=hashlib.sha256((Path(a.checkout)/item['path']).read_bytes()).hexdigest()
        if actual!=item['sha256']:raise SystemExit('source hash mismatch: '+item['path'])
    print(json.dumps({'commit':commit,'verified_files':len(manifest['files']),'status':'PASS'},sort_keys=True))


if __name__=='__main__':main()
