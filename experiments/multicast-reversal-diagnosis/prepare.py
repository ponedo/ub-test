"""Clone only the two authorized 3136-Gbps immutable real inputs, privately."""
import argparse
from common import *
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--stage-a',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();b=a.build.resolve();gate=a.stage_a.resolve()/'status.json';g=json.loads(gate.read_text());assert g['status']=='PASS'
for identity in g['identities'].values():check(identity)
check(g['input_identity']);o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
ledger=dict(status='PREPARED',link_gbps=3136,build=str(b),stage_a_path=str(gate),stage_a_sha256=sha(gate),identities=g['identities'],runs=[])
for mode in ['chunk-streaming','multicast-v2']:
 src=ACCEPTED/'real-3136'/mode;d=o/mode;copy_inputs(src,d)
 baseline=json.loads((src/'run-result.json').read_text());assert baseline['status']=='PASS'
 cfg=json.loads((d/'config.json').read_text());assert all(cfg[x]['link_gbps']==3136 for x in ['runtime','parameters']);assert (d/'input.txt').read_text().split()[12]=='3136'
 # Freeze full baseline evidence and private execution inputs; neither is regenerated.
 evidence=freeze([src/n for n in INPUTS+['online-summary.json','expert-compute.csv','expert-ready.csv','replica-ready.csv','run-result.json']])
 ledger['runs'].append(dict(strategy=mode,status='PREPARED',baseline=str(src),baseline_identity=evidence,immutable_files=freeze([d/n for n in INPUTS])))
write(o/'ledger.json',ledger)
