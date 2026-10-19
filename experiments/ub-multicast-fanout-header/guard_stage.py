#!/usr/bin/env python3
"""Run one support stage with the same established experiment resource guard."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args();cmd=a.command[1:] if a.command[:1]==['--'] else a.command
if not cmd or a.out.exists():raise SystemExit('fresh output and command required')
a.out.parent.mkdir(parents=True,exist_ok=True)
r=run(cmd,a.out,3600,case=a.out.parent)
raise SystemExit(0 if r['status']=='PASS' else 2)
