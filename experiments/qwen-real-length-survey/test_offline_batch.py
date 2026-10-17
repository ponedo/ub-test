"""Synthetic fixtures only. Nothing here is actual QwenTrace statistics."""
import copy
import csv
import hashlib
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import offline_batch as b


def source(n, offset=0):
    return [{str(layer): [[(offset+layer+t+i)%128 for i in range(8)] for t in range(n)] for layer in range(94)},
            {str(layer): [[(layer+i)%128 for i in range(8)]] for layer in range(94)}]

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.manifest={'phase_documentation':'SYNTHETIC TEST fixture only', 'requests':[]}
        for i,n in enumerate((130,140)):
            path=self.root/f'{i}.json'; raw=json.dumps(source(n,i)).encode(); path.write_bytes(raw)
            self.manifest['requests'].append(dict(request_id=f'synthetic_{i}',dataset_path=f'SYNTHETIC/{i}.json',revision='a'*40,expected_blob_sha=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest(),file_path=str(path)))
        self.path=self.root/'input-manifest.json'; self.write()
    def tearDown(self): self.temp.cleanup()
    def write(self): self.path.write_text(json.dumps(self.manifest))
    def run_batch(self, **kwargs): return b.run(self.path,self.root/'private',self.root/'stats',reserve=0,**kwargs)
    def test_end_to_end_boundaries_and_same_layer(self):
        result=self.run_batch(export_layers=(0,93))
        self.assertEqual(result['batch_tokens'],270)
        self.assertTrue(result['prefixes']['256']['available'])
        self.assertFalse(result['prefixes']['512']['available'])
        self.assertEqual([x['selected_tokens'] for x in result['prefixes']['256']['boundaries']],[130,126])
        for layer in (0,93):
            with (self.root/f'private/batch/layer_{layer}.csv').open() as f: rows=list(csv.DictReader(f))
            self.assertEqual(rows[130]['request_id'],'synthetic_1')
            self.assertEqual(rows[130]['token_ordinal'],'0')
            self.assertEqual(int(rows[130]['expert_0']),(layer+1)%128)
        self.assertFalse((self.root/'private/batch/layer_1.csv').exists())
        with gzip.open(self.root/'stats/layer-statistics.csv.gz','rt',newline='') as f:
            self.assertTrue(list(csv.DictReader(f)))
        self.assertFalse((self.root/'stats/layer-statistics.csv').exists())
    def test_lossless_deterministic_gzip(self):
        raw=b'selection,dataset,layer\na,real,0\n'
        a=self.root/'a.csv'; a.write_bytes(raw)
        proof=b.compress_aggregate(a)
        self.assertFalse(a.exists())
        with gzip.open(self.root/proof['file'],'rb') as f: self.assertEqual(f.read(),raw)
        second=self.root/'b.csv'; second.write_bytes(raw)
        again=b.compress_aggregate(second)
        self.assertEqual(proof['compressed_sha256'],again['compressed_sha256'])
        self.assertEqual(proof['uncompressed_sha256'],hashlib.sha256(raw).hexdigest())
    def test_missing_metadata(self):
        for field in ('request_id','dataset_path','revision','expected_blob_sha','file_path'):
            old=self.manifest['requests'][0].pop(field); self.write()
            with self.assertRaises(ValueError): b.manifest_read(self.path)
            self.manifest['requests'][0][field]=old
    def test_missing_phase(self):
        del self.manifest['phase_documentation'];self.write()
        with self.assertRaises(ValueError): b.manifest_read(self.path)
    def test_duplicate_request_source(self):
        for field in ('request_id','file_path','expected_blob_sha','dataset_path'):
            old=self.manifest['requests'][1][field]
            self.manifest['requests'][1][field]=self.manifest['requests'][0][field]; self.write()
            with self.assertRaises(ValueError): b.manifest_read(self.path)
            self.manifest['requests'][1][field]=old
    def test_bad_blob(self):
        self.manifest['requests'][0]['expected_blob_sha']='b'*40; self.write()
        with self.assertRaisesRegex(ValueError,'blob mismatch'): self.run_batch()
    def test_bound_before_creation(self):
        with self.assertRaisesRegex(ValueError,'guard'): self.run_batch(private_cap=1)
        self.assertFalse((self.root/'private').exists())
    def test_bad_layers(self):
        for layers in ((0,0),(94,),()):
            with self.assertRaises(ValueError): self.run_batch(export_layers=layers)
    def test_malformed_raw(self):
        bad=[]
        data=source(2); data[0]['0'][0][1]=data[0]['0'][0][0];bad.append(data)
        data=source(2); data[0]['0'][0][0]=128;bad.append(data)
        data=source(2); data[0]['0'][0][0]=True;bad.append(data)
        data=source(2); del data[0]['93'];bad.append(data)
        data=source(2); data[0]=dict(reversed(list(data[0].items())));bad.append(data)
        data=source(2); data[0]['0'].pop();bad.append(data)
        data=source(2); data[1]['0'].append(data[1]['0'][0]);bad.append(data)
        for data in bad:
            path=self.root/'bad.json'; path.write_text(json.dumps(data))
            with self.assertRaises(ValueError): b.validator.read_source(path)
    def test_independent_metrics(self):
        for values in ([8]*128,[1024]+[0]*127,list(range(128))):
            a=b.extract.metrics(values);c=b.independent_counts_metrics(values)
            for key in a:self.assertAlmostEqual(a[key],c[key],places=12)
    def test_reject_tampered_batch_order_crosslayer_and_duplicate(self):
        rows=[['r','0','0','1'],['r','1','1','2']]
        for changed in (list(reversed(rows)), rows[:1], [['r','0','9','10'],rows[1]]):
            with self.assertRaises(ValueError): b.verify_batch_rows(changed,rows,2)
        duplicate=[rows[0],rows[0]]
        with self.assertRaisesRegex(ValueError,'duplicate'): b.verify_batch_rows(duplicate,duplicate,2)
    def test_duplicate_json_key(self):
        self.path.write_text('{"requests":[],"requests":[]}')
        with self.assertRaises(ValueError): b.manifest_read(self.path)

if __name__=='__main__': unittest.main()
