"""Synthetic fixtures only; no dataset routes embedded."""
import copy,json,unittest
import extract

class ParseTests(unittest.TestCase):
    def fixture(self):
        return [{str(i):[list(range(8)),list(range(8,16))] for i in range(94)},
                {str(i):[list(range(8))] for i in range(94)}]
    def reject(self,edit):
        x=self.fixture();edit(x)
        with self.assertRaises(ValueError):extract.parse(json.dumps(x))
    def test_valid(self):self.assertEqual(extract.parse(json.dumps(self.fixture())),self.fixture())
    def test_missing_layer(self):self.reject(lambda x:x[0].pop('12'))
    def test_wrong_topk(self):self.reject(lambda x:x[0]['0'][0].pop())
    def test_duplicate_expert(self):self.reject(lambda x:x[0]['0'][0].__setitem__(1,0))
    def test_negative_expert(self):self.reject(lambda x:x[0]['0'][0].__setitem__(1,-1))
    def test_large_expert(self):self.reject(lambda x:x[0]['0'][0].__setitem__(1,128))
    def test_bool_expert(self):self.reject(lambda x:x[0]['0'][0].__setitem__(1,True))
    def test_string_expert(self):self.reject(lambda x:x[0]['0'][0].__setitem__(1,'1'))
    def test_layer_token_mismatch(self):self.reject(lambda x:x[0]['0'].pop())
    def test_decode_multitoken(self):self.reject(lambda x:x[1]['0'].append(list(range(8))))
    def test_reordered_layers(self):self.reject(lambda x:x[0].update({'0':x[0].pop('0')}))
    def test_duplicate_json_key(self):
        with self.assertRaises(ValueError):extract.parse('[{"0": [], "0": []}]')
    def test_uniform_metrics(self):
        m=extract.metrics([8]*128)
        for k,v in [('max_mean',1),('jain',1),('gini',0),('cv',0)]:self.assertEqual(m[k],v)
    def test_concentrated_metrics(self):
        m=extract.metrics([128]+[0]*127)
        self.assertEqual(m['jain'],1/128);self.assertEqual(m['gini'],127/128)

if __name__=='__main__':unittest.main()
