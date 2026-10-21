"""Import immutable v1 helpers; no copied transport, planner, or guard framework."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
V1 = HERE.parent / 'chunk-streaming-multicast'
sys.dont_write_bytecode = True
sys.path.insert(0, str(V1))
from common import *
BASE_V1 = 'e3efc29e901024cea6343196f6ab33958e3b02cd'
CONTROL_SHA256 = '2fd21591e56bf8bd9dfe7ee481e5ce935ac776722ba1e3193acb38ee0d6e5b2f'
import fixtures, phase_b, preflight, adapter, verify, phase_b_reproduce

def declaration():
    import copy
    old = fixtures.matrix()
    selected = ['B01','B02','B03','B04','B05','B06','B09','B10','B12','F01','F02','F03','F04','F05']
    byid = {r['id']:r for r in old['rows']}
    rows = []
    for i, ident in enumerate(selected, 1):
        row = copy.deepcopy(byid[ident])
        row.update(id=f'V{i:02d}', retained_id=ident, arms=['v1','candidate-on'])
        if ident == 'B10':
            row['required_witnesses'] = ['ta_window_512','resource_cleanup']
        rows.append(row)
    for ident in ['V01','V04','V06']:
        row = copy.deepcopy(next(r for r in rows if r['id']==ident))
        row.update(id='C-'+ident, reference=ident, arms=['candidate-off'], kind='parity')
        rows.append(row)
    for ident in ['N02','N04','N08']:
        row=copy.deepcopy(byid[ident]);row.update(retained_id=ident,arms=['v1','candidate-on']);rows.append(row)
    specs={r['fixture']:copy.deepcopy(old['fixtures'][r['fixture']]) for r in rows}
    specs['reuse-window']['relay']['chunk_bytes']=4096
    specs['reuse-window']['topology']={}
    specs['reuse-window']['required_witnesses']=['ta_window_512','resource_cleanup']
    for spec in specs.values():
        spec['model'].update(link_gbps=3136,link_delay_ns=20)
        require(spec['relay']['chunk_bytes']==4096,'Fixed chunk scope')
        require(len(spec['planner_input']['mapping'])<=200 and spec['planner_input']['npus']<=20,'Small synthetic scope')
    require(sum(len(r['arms']) for r in rows)==37,'Exact bounded run count')
    return dict(base=BASE_V1,status='PLANNED_NOT_EXECUTED',rows=rows,fixtures=specs,budget=fixtures.BUDGET,
                executions=37, treatment='query-triggered per-head one-shot 5ns Stage I/II APP eligibility hold',
                candidate_flag='--cs-mc-align-hold',chunk_bytes=4096,native_ta_window=512,link_gbps=3136,link_delay_ns=20,native_allocation_ns=5,tp_packet_window=1000)
