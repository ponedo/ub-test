#!/usr/bin/env python3
"""Use accepted preparation unchanged; select the accepted multicast graph adapter."""
import argparse, subprocess,sys,json,os,importlib.util
from pathlib import Path
E=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--counts',type=Path,required=True);p.add_argument('--layer',type=int,required=True);p.add_argument('--strategy',choices=['no-balancing','direct','chunk-streaming','multicast'],required=True);a=p.parse_args()
cmd=[sys.executable,E/'qwen-real-minimal/prepare.py','--routing',a.reference/'routing'/f'layer_{a.layer}.json','--out',a.out,'--graph-tool',a.graph_tool,'--tokens',2048,'--layer',a.layer,'--source-manifest',a.manifest,'--frozen-counts',a.counts,'--strategy','direct' if a.strategy=='multicast' else a.strategy]
subprocess.run(list(map(str,cmd)),check=True)
if a.strategy=='multicast':
 spec=importlib.util.spec_from_file_location('accepted_relay_adapter',E/'multi-npu-relay/adapter.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 os.environ['RELAY_GRAPH_TOOL']=str(a.graph_tool.resolve());fixed=json.loads((E/'qwen-prefill-token-scaling/fixed-config.json').read_text());m.emit(a.out/'direct-input',fixed['relay_parameters'],'multicast',a.out/'multicast-run')
