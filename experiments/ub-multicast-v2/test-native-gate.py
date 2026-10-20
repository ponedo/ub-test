#!/usr/bin/env python3
import copy, importlib.util, json
from pathlib import Path
s=importlib.util.spec_from_file_location('gate',Path(__file__).with_name('check-native.py')); m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
names=['unified-bus-a','unified-bus-examples','unified-bus-z']
rows=[dict(suite=n,status='PASS',returncode=0,guard=None) for n in names]
rows[1].update(status='FAIL',returncode=1)
console='FAIL unified-bus-examples 1 s\n  FAIL UnifiedBus - ub-quick-example local dependency visibility delay applies 1 s\n test="hasTaskTimes (actual) == true (limit)" actual="0" limit="1" dependent tasks should have start/finish times'
base=[rows,names,dict(guard=None,returncode=1),console,False]
assert m.validate(*base)==['unified-bus-examples']
mutations=[]
x=copy.deepcopy(base);x[0]=x[0][:2];mutations.append(x)
x=copy.deepcopy(base);x[0][1]['guard']='wall';mutations.append(x)
x=copy.deepcopy(base);x[2]['guard']='rss';mutations.append(x)
x=copy.deepcopy(base);x[2]['returncode']=0;mutations.append(x)
x=copy.deepcopy(base);x[0][1]['returncode']=-9;mutations.append(x)
x=copy.deepcopy(base);x[3]=console.replace('hasTaskTimes','different');mutations.append(x)
x=copy.deepcopy(base);x[3]+='\n FAIL another test';mutations.append(x)
x=copy.deepcopy(base);x[4]=True;mutations.append(x)
x=copy.deepcopy(base);x[0][0]['returncode']=1;mutations.append(x)
x=copy.deepcopy(base);x[0].reverse();mutations.append(x)
for x in mutations:
 try:m.validate(*x)
 except AssertionError:pass
 else:raise RuntimeError('invalid native result accepted')
ok=copy.deepcopy(base)
ok[0][1].update(status='PASS',returncode=0);ok[2]['returncode']=0;assert m.validate(*ok)==[]
print(json.dumps(dict(valid=2,rejected=len(mutations),status='PASS')))
