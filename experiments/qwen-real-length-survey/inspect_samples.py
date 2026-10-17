"""Validate explicitly selected authorized local files; no network or secret access."""
import argparse,csv,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qwen-real-prefill-trace'))
from extract import parse
from independent_validator import read_source

def inspect(path,expected_bytes,expected_blob):
    raw=path.read_bytes()
    if len(raw)!=expected_bytes: raise ValueError('public metadata byte size mismatch')
    blob=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
    identity='raw Git blob'
    if blob!=expected_blob:
        pointer=f'version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(raw).hexdigest()}\nsize {len(raw)}\n'.encode()
        pointer_blob=hashlib.sha1(f'blob {len(pointer)}\0'.encode()+pointer).hexdigest()
        if pointer_blob!=expected_blob: raise ValueError('public metadata blob mismatch for raw content and LFS pointer')
        identity='Git LFS pointer reconstructed from actual SHA256 and size matches public blob'
    else: pointer_blob=None
    parsed=parse(raw)
    independent_raw, independent=read_source(path)
    if independent_raw!=raw or independent!=parsed: raise ValueError('independent parser disagreement')
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),git_blob=blob,
                identity_verification=identity,public_git_blob=expected_blob,lfs_pointer_git_blob=pointer_blob, tokens_per_layer=len(parsed[0]['0']),layers=94,top_k=8,records=len(parsed),
                later_single_row_records=len(parsed)-1,
                phase='record 0 follows documented prefill convention; no embedded phase labels',
                token_identity='serialized row ordinal; original tokenizer ID unverified',
                validation='extract.parse and independent_validator.read_source both pass')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,required=True);ap.add_argument('--shortlist',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    with a.shortlist.open() as f: candidates=list(csv.DictReader(f))
    results=[]
    for row in candidates:
        result=inspect(a.input_root/row['path'],int(row['bytes']),row['git_blob'])
        result.update(source_path=row['path'],revision='27febb7b2d24169560a9f6f83d38eb53f94916cf',access='authorized Hugging Face device-login CLI; original private')
        results.append(result); print(json.dumps(result),flush=True)
    a.output.write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()
