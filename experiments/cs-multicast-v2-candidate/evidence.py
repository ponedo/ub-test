"""Small additional native accounting and disabled deterministic parity checks."""
from collections import defaultdict
from support import *

def native_accounting(directory):
    status=read(directory/'diagnostic-status.json')
    require(status['enabled'] and not status['incomplete'],'INCOMPLETE native diagnostics')
    for key in ['open_interval_keys','queue_observations_open','queue_unmatched','queue_order_errors','queue_depth_errors','grant_outcomes_unmatched','grant_start_overwrites','grant_starts_open']:
        require(status[key]==0,'INCOMPLETE native diagnostics '+key)
    ports=defaultdict(lambda:defaultdict(lambda:[0,0]))
    for r in phase_b.csv_rows(directory,'diagnostic-native-aggregates.csv'):
        metric=int(r['metric']);values=ports[int(r['node']),int(r['port'])][metric]
        values[0]+=int(r['count']);values[1]+=int(r['sum'])
    results=[]
    for (node,port),m in sorted(ports.items()):
        requested,effective,rejected,noingress,tx=(m[k][0] for k in [2,10,8,9,4])
        require(requested==effective+rejected+noingress,'Native grant outcome conservation')
        require(effective==tx,'Native effective grant / physical TX count')
        results.append(dict(node=node,port=port,requested=requested,effective=effective,rejected=rejected,no_ingress=noingress,
                            rejected_elapsed_ps=m[8][1],no_ingress_elapsed_ps=m[9][1],requested_service_ps=m[2][1]))
    return dict(status='PASS',ports=results,tail_overwrites=status['tail_overwrites'],rolling_tail_complete=status['tail_overwrites']==0,tail_limitation='Rolling native tail is sampled; evicted events cannot support complete causal chains. Aggregate accounting and global Jetty occupancy are independent.',semantics='Whole-run counts; rejected/no-ingress elapsed are not member-wait attribution.')

def disabled_parity(reference,directory):
    result=phase_b.parity(reference,directory)
    # Observer-only candidate files and host measurement fields are excluded.
    # Every deterministic legacy physical/timeline/compute payload is unchanged.
    names=['hybrid-summary.json','hybrid-groups.csv','hybrid-stats.csv','hybrid-fallback.csv',
           'hybrid-physical.csv','hybrid-events.csv','events.csv','diagnostic-native-aggregates.csv',
           'diagnostic-port-partition.csv','diagnostic-weight-phase-cohorts.csv']
    checked=[]
    for name in names:
        a,b=reference/name,directory/name
        require(a.exists()==b.exists(),'Disabled artifact presence differs '+name)
        if a.exists():require(a.read_bytes()==b.read_bytes(),'Disabled deterministic parity differs '+name);checked.append(name)
    result['extra_byte_identical_files']=checked
    return result
