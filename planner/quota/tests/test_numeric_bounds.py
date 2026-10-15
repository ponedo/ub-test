#!/usr/bin/env python3
"""Validation only: never materialize a large trace or invoke the C++ engine."""
import json,sys,math
from ctypes import c_float
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from planner import validate_upstream_numeric,InputError,solve
from unittest.mock import patch

def need(ok,message):
    if not ok:raise RuntimeError(message)
def accepted(total,g=72,beta='100',eps='100',search=True):
    try:return validate_upstream_numeric(total,g,beta,eps,search)
    except InputError:return None

# The original reported failure, evaluated only with Python unbounded integers.
f=lambda x:c_float(x).value
total=300000;g=72
lower=math.ceil(f(f(f(total)/g)*f(100)))
threshold=math.ceil(f(f(lower)*f(f(1)+f(100))))
slack=g*threshold-total
need(threshold<2**31-1 and slack>2**31-1,'reported aggregate overflow not reproduced arithmetically')
need(accepted(total) is None,'unsafe aggregate accepted')
# Adjacent boundary inputs of the explicit conservative support domain.
lo,hi=0,2000000
while lo<hi:
    mid=(lo+hi+1)//2
    if accepted(mid):lo=mid
    else:hi=mid-1
need(accepted(lo) is not None and accepted(lo+1) is None,'boundary pair')
# Normal parameters retain the entire wrapper's two-million assignment domain.
for g in [1,2,33,64,65,72]:
    need(accepted(2000000,g,'1.01','.01',g>1) is not None,'normal maximum rejected')
need(accepted(300000,72,'100','100',False) is not None,'no-search bypass unnecessarily rejected')
need(accepted(0) is not None,'empty rejected')
need(accepted(2000001) is None,'assignment cap ignored')
# Independently inspect actual float32 arithmetic at and around conservative
# boundaries for diverse parameters; no C++ execution takes place.
checked=0
for g in [2,33,64,65,72]:
 for beta in ['1','1.01','10','100']:
  for eps in ['0','.01','1','100']:
   for t in [0,1,lo,lo+1,300000,2000000]:
    bound=accepted(t,g,beta,eps)
    if bound is None:continue
    lower=math.ceil(f(f(f(t)/g)*f(float(beta))))
    fast=math.ceil(f(f(lower)*f(f(1)+f(float(eps)))))
    highest=max(t,lower,fast)
    need(g*highest<=2**31-1 and highest<=bound['upper_threshold'],'float32 threshold escaped bound')
    need(highest+max(1,(max(t,lower)+99)//100)<=2**31-1,'retry addition unsafe')
    checked+=1
# Confirm the public solve path cannot skip preflight; this uses no token data.
with patch('planner.validate_upstream_numeric',side_effect=InputError('preflight sentinel')) as preflight:
    try:solve(dict(schema_version=1,npus=2,experts=2,top_k=1,main_placement=[0,1],slots=[1,1],mapping=[]))
    except InputError as error:need(str(error)=='preflight sentinel','preflight did not guard solve')
    else:raise RuntimeError('preflight bypassed')
    need(preflight.call_count==1,'preflight call count')
report=dict(status='PASS',method='validation-only arithmetic; no large trace and no unsafe C++ execution',
            reported_case=dict(assignments=300000,ranks=72,beta=100,epsilon=100,fast_threshold=threshold,aggregate_slack=slack,rejected=True),
            conservative_boundary=dict(last_allowed=lo,first_rejected=lo+1,allowed_bounds=accepted(lo)),
            safe_parameter_samples=checked,normal_full_domain=True,bypass=True)
(R/'evidence/numeric-bounds.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
