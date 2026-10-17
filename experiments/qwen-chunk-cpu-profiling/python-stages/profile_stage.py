#!/usr/bin/env python3
"""Diagnostic-only cProfile runner; unchanged algorithm and guard-compatible SIGTERM dump.

AST adds one context-manager around each top-level statement of selected adapter
and independent-check functions, and preparation's module statements. It never
changes expressions, loops, assertions, algorithms, input or validation policy.
Nested stage durations overlap: do not sum across different scope prefixes.
"""
import argparse, ast, builtins, cProfile, csv, hashlib, importlib.machinery, json, os, resource, signal, sys, time
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('script',type=Path);p.add_argument('args',nargs=argparse.REMAINDER);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=True)
rows=[];sources={};interrupted=None;stack=[]
class Span:
 def __init__(self,label):self.label=label
 def __enter__(self):
  self.wall=time.perf_counter();self.cpu=time.process_time();self.ru=resource.getrusage(resource.RUSAGE_SELF);stack.append(self.label);return self
 def __exit__(self,typ,value,tb):
  ru=resource.getrusage(resource.RUSAGE_SELF)
  rows.append(dict(stage=self.label,depth=len(stack),wall_seconds=time.perf_counter()-self.wall,cpu_seconds=time.process_time()-self.cpu,user_cpu_seconds=ru.ru_utime-self.ru.ru_utime,system_cpu_seconds=ru.ru_stime-self.ru.ru_stime,peak_rss_kib=ru.ru_maxrss,status='COMPLETE' if typ is None else 'INTERRUPTED' if typ is SystemExit else 'EXCEPTION'))
  stack.pop()
builtins.__qwen_profile_span__=Span
TARGETS={'multi-npu-relay/adapter.py':{'emit'},'direct-weight-forward/adapter.py':{'emit'},'tiered-logging/preflight.py':{'check','canonical_graph','input_summary'}}
def wrap(statements,prefix,source):
 result=[]
 for node in statements:
  if isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef,ast.ClassDef)) or (isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant)):
   result.append(node);continue
  label=f'{prefix}:{node.lineno}: '+source.splitlines()[node.lineno-1].strip()[:130]
  wrapped=ast.With(items=[ast.withitem(context_expr=ast.Call(func=ast.Name(id='__qwen_profile_span__',ctx=ast.Load()),args=[ast.Constant(label)],keywords=[]),optional_vars=None)],body=[node])
  result.append(ast.copy_location(wrapped,node))
 return result
def compiled(path):
 path=Path(path);source=path.read_text();tree=ast.parse(source,filename=str(path));suffix='/'.join(path.parts[-2:]);sources[str(path)]=hashlib.sha256(source.encode()).hexdigest()
 if suffix=='qwen3-model-size/prepare.py':tree.body=wrap(tree.body,suffix,source)
 else:
  for node in tree.body:
   if isinstance(node,ast.FunctionDef) and node.name in TARGETS.get(suffix,set()):node.body=wrap(node.body,suffix+'::'+node.name,source)
 ast.fix_missing_locations(tree);return compile(tree,str(path),'exec')
old=importlib.machinery.SourceFileLoader.get_code
def get_code(loader,name):
 if any(loader.path.endswith(suffix) for suffix in TARGETS):return compiled(loader.path)
 return old(loader,name)
importlib.machinery.SourceFileLoader.get_code=get_code
prof=cProfile.Profile();start=time.perf_counter();cpu=time.process_time();status='COMPLETE';exitcode=0

def terminate(signum,frame):
 global interrupted
 interrupted=dict(signal=signum,file=frame.f_code.co_filename,line=frame.f_lineno,function=frame.f_code.co_name,active_stages=list(stack))
 raise SystemExit(128+signum)
signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
script=a.script.resolve();sys.argv=[str(script)]+a.args;sys.path.insert(0,str(script.parent))
try:
 prof.enable();exec(compiled(script),{'__name__':'__main__','__file__':str(script),'__package__':None})
except SystemExit as ex:
 exitcode=ex.code or 0;status='INTERRUPTED' if interrupted else 'COMPLETE' if exitcode==0 else 'FAILED'
except BaseException:
 status='FAILED';exitcode=1;raise
finally:
 prof.disable();prof.dump_stats(str(a.out/'profile.pstats'))
 with (a.out/'stages.csv').open('w') as f:
  fields=['stage','depth','wall_seconds','cpu_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','status'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 (a.out/'coverage.json').write_text(json.dumps(dict(status=status,exitcode=exitcode,interrupted=interrupted,wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,profile_clock='wall',source_sha256=sources,command=sys.argv,coverage='Python main process; subprocess waits included, child internals excluded',stage_note='Inclusive statement spans; nested scopes overlap; RSS is cumulative process high-water mark'),indent=2)+'\n')
sys.exit(exitcode)
