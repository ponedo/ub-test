import hashlib,json,tempfile,unittest
from pathlib import Path
from inspect_samples import inspect
class InspectTests(unittest.TestCase):
    def test_exact_local_identity_and_shape(self):
        data=[{str(i):[list(range(8)) for _ in range(n)] for i in range(94)} for n in (3,1)]
        raw=json.dumps(data).encode();blob=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.json';p.write_bytes(raw)
            result=inspect(p,len(raw),blob)
            self.assertEqual(result['tokens_per_layer'],3)
            self.assertEqual(result['later_single_row_records'],1)
            pointer=f'version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(raw).hexdigest()}\nsize {len(raw)}\n'.encode()
            pointer_blob=hashlib.sha1(f'blob {len(pointer)}\0'.encode()+pointer).hexdigest()
            lfs=inspect(p,len(raw),pointer_blob)
            self.assertEqual(lfs['lfs_pointer_git_blob'],pointer_blob)
            self.assertEqual(lfs['sha256'],result['sha256'])
            with self.assertRaisesRegex(ValueError,'byte size'):inspect(p,len(raw)+1,blob)
            with self.assertRaisesRegex(ValueError,'blob mismatch'):inspect(p,len(raw),'0'*40)
if __name__=='__main__':unittest.main()
