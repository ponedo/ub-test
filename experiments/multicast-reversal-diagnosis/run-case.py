"""One bounded, private diagnostic real run with exact accepted evidence checks."""
import argparse,time
from common import *
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('mode',choices=['chunk-streaming','multicast-v2']);p.add_argument('--build',type=Path,required=True);a=p.parse_args();r=a.root.resolve();b=a.build.resolve();d=r/a.mode;l=json.loads((r/'ledger.json').read_text());record=next(x for x in l['runs'] if x['strategy']==a.mode);assert record['status']=='PREPARED';assert str(b)==l['build'];assert l['link_gbps']==3136
start=time.monotonic()
def identities():
 for x in l['identities'].values():check(x)
 check(record['baseline_identity']);check(record['immutable_files']);assert sha(l['stage_a_path'])==l['stage_a_sha256'];assert json.loads(Path(l['stage_a_path']).read_text())['status']=='PASS'
def save():write(d/'run-result.json',record)
def stage(cmd,path):
 remaining=4800-(time.monotonic()-start)
 assert remaining>0,'4800 second whole-case wall guard'
 result=run(cmd,path,remaining,case=r);assert result['status']=='PASS','guard/nonzero '+str(path);return result
try:
 identities();record['status']='RUNNING';save()
 stage([sys.executable,OLD/'preflight.py',d,'--graph-tool',b/'graph-tool'],d/'preflight-host')
 record['simulator_host']=stage(simulator(b,d,'on',False,['--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000']),d/'simulator-host');save()
 validate(stage,b,d);parity(Path(record['baseline']),d)
 assert (d/'diagnostic-status.json').is_file(),'Missing recorder completeness status'
 record['diagnostic_status']=validate_diagnostics(d)
 assert record['diagnostic_status']['enabled'] is True and record['diagnostic_status']['incomplete'] is False,'Incomplete bounded recorder evidence'
 record['timeline_note']='Tail is a bounded ring; overwritten earlier events are unavailable. No continuous-stall inference from polling.'
 identities();record.update(status='PASS',case_wall_seconds=time.monotonic()-start,summary=json.loads((d/'online-summary.json').read_text()),metrics=json.loads((d/'simulator-metrics.json').read_text()),exact_baseline_parity=True);save();print('VERIFIED',a.mode,flush=True)
except BaseException as e:record.update(status='FAIL',failure=str(e));save();raise
