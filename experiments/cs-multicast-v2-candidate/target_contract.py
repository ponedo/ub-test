"""Fixed requested high-bandwidth target, not a bandwidth sweep."""
import shutil
from support import *

def check_target(directory,executed=False):
    directory=Path(directory);c=read(directory/'config.json')
    for group in ['parameters','runtime']:
        require(c[group]['link_gbps']==3136,'Target link must be3136Gbps: '+group)
        require(c[group]['link_delay_ns']==20,'Target link delay must be20ns')
        require(c[group]['chunk_bytes']==4096,'Target chunk must be4096bytes')
    fields=(directory/'input.txt').read_text().splitlines()[0].split()
    require(len(fields)==14 and int(fields[12])==3136 and int(fields[13])==20,'Serialized network target differs from config')
    require(c['planner_input']['npus']<=20 and len(c['planner_input']['mapping'])<=200,'Small synthetic scope')
    if executed:
        actual=read(directory/'ablation-config.json')
        require(actual['jetty_ta_window']==512 and actual['tp_packet_window']==1000,'Actual TA/TP window drift')
        native=phase_b.csv_rows(directory,'diagnostic-native-aggregates.csv')
        grants=[r for r in native if int(r['metric'])==2]
        require(grants and all(int(r['sum'])==5000*int(r['count']) for r in grants),'Actual requested allocator service differs from5ns')
    return dict(status='PASS',link_gbps=3136,link_delay_ns=20,chunk_bytes=4096,ta_window=512,tp_packet_window=1000,native_allocation_ns=5,actual_native_parameters_verified=executed)

def reuse_balanced_base(source,dest):
    source,dest=Path(source),Path(dest);require(source.is_dir() and not dest.exists(),'Fresh destination and retained planner source required')
    shutil.copytree(source,dest)
    c=read(dest/'config.json')
    for key in ['parameters','runtime']:
        require(c[key]['link_gbps']==100 and c[key]['link_delay_ns']==20,'Only recorded off-target100Gbps source may be corrected')
        c[key]['link_gbps']=3136
    write(dest/'config.json',c)
    lines=(dest/'input.txt').read_text().splitlines();f=lines[0].split()
    require(len(f)==14 and f[12]=='100' and f[13]=='20','Unexpected retained serialized network')
    f[12]='3136';lines[0]=' '.join(f);(dest/'input.txt').write_text('\n'.join(lines)+'\n')
    for name in ['plan.json','assignments.csv','transfers.csv']:
        require((source/name).read_bytes()==(dest/name).read_bytes(),'Planner decision modified')
