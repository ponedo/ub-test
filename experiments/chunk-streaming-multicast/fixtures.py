#!/usr/bin/env python3
"""Frozen small correctness inputs. Importing this file starts no process or solver."""
import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from common import HYBRID, RELAY, require, semantic, write

SCHEMA = 1
BUDGET = dict(tree_rss_bytes=6*1024**3, address_space_bytes=7*1024**3,
              wall_seconds=4800, min_host_available_bytes=1024**3,
              min_disk_free_bytes=8*1024**3, min_tmp_disk_free_bytes=2*1024**3)
OLD_MODES = ('no-balancing', 'direct', 'chunk-streaming', 'multicast-v2')
REGRESSION_FIXTURES = ('zero', 'two-hop', 'tail')
# This is the accepted executable identity, not a rebuilt approximation.
ACCEPTED_BINARY_SHA256 = '27b3eae2b2aa7cd3c932359261c410238ae53beb4a752ca0d1e62e225befc85b'
PARITY_FIELDS = ('layer_latency_ps','remote_WQEs','TA_count','target_segments',
    'sender_completions','completed_tokens','assignments','replicas','jettys',
    'combine_fnv1a64','executed_graph_fnv1a64','max_npu_load','per_npu_load',
    'verified_bytes','remote_bytes','local_bytes','packet_tx_per_node',
    'packet_rx_per_node','byte_tx_per_node','byte_rx_per_node','timeline',
    'stage_intervals','compute_intervals')
PARITY_FILES = ('packet-counts.csv','replica-ready.csv','pair-state.csv','network-resources.csv',
                'queue-stats.csv','expert-compute.csv','expert-ready.csv')


def loads(n, per_rank, counts, slots=1):
    require(len(counts) == n*per_rank, 'Synthetic expert dimension')
    return dict(schema_version=1, npus=n, experts=n*per_rank, top_k=1,
        main_placement=[x//per_rank for x in range(n*per_rank)], slots=[slots]*n,
        mapping=[dict(source=(i+expert)%n, experts=[expert])
                 for expert,count in enumerate(counts) for i in range(count)],
        beta='1.01', min_replica_quota=1024)


def definitions():
    hot4 = loads(4, 1, [32,0,0,0])
    hot8 = loads(8, 1, [64]+[0]*7)
    def item(planner, model=None, relay=None, expect=None, witnesses=(), log='summary'):
        return dict(planner_input=planner, model=dict({'weight_bytes':12288}, **(model or {})),
            relay=dict(RELAY, **(relay or {})), topology=expect or {},
            required_witnesses=list(witnesses), log_level=log)
    # Matrix-exact tail intentionally omits synthetic weight_bytes.
    tail = item(hot4, relay=dict(force_relay=True, chunk_bytes=2000),
                expect=dict(min_stage2_groups=1, tail=True, shard_tail=True),
                witnesses=('tail_ranges','nondivisible_shard'), log='events')
    tail['model'] = dict(model_dim=65, ff_dim=129, segment_bytes=333)
    return {
      'zero': item(loads(4,1,[32,0,0,0],slots=0), expect=dict(groups=0), witnesses=('zero_replicas',)),
      'singleton': item(loads(4,1,[8,0,4,4]), expect=dict(fanout=1, groups=1), witnesses=('singleton_native',)),
      'fallback': item(hot4, expect=dict(direct_fanout=3), witnesses=('fanout3','direct_fallback'), log='events'),
      'two-hop': item(hot8, expect=dict(stage1_fanout=2, stage2_fanout=2, min_relays=2),
          witnesses=('fanout2','stage1_envelope','stage2_envelope','multiple_relays','streaming_physical'), log='events'),
      'slow-relay': item(hot8, relay=dict(slow_relay_rank=1,slow_relay_ns=20000),
          expect=dict(stage1_fanout=2,stage2_fanout=2,min_relays=2),
          witnesses=('groupchunk_all_parents',), log='events'),
      'multi-expert': item(loads(8,2,[64,64]+[0]*14,slots=3),
          relay=dict(force_relay=True), expect=dict(min_experts=2,min_stage2_groups=2),
          witnesses=('concurrent_experts','cross_expert_chunk_isolation'), log='events'),
      'tail': tail,
      'reordered-ready': item(hot4, relay=dict(force_relay=True,reorder_ns=20000),
          expect=dict(min_stage2_groups=1), witnesses=('completion_reorder',), log='events'),
      'fanout-four': item(loads(20,1,[200]+[0]*19),
          expect=dict(stage1_fanout=4), witnesses=('fanout4',), log='events'),
      # 64 tokens, fixed 512 native TA window, 1058 short chunks. This is NOT a
      # real-token N512/N1024 experiment and does not change the native window.
      'reuse-window': item(hot8, model=dict(weight_bytes=1057*1024+1,weight_completion_ns=200000),
          relay=dict(chunk_bytes=1024), expect=dict(min_groups=1025,min_pair_tas=513),
          witnesses=('ta_window_512','lifetime_groups_gt1024','resource_cleanup')),
    }


FAULTS = (
    dict(id='F01', fixture='two-hop', fault='data-once', role='stage1', witness='fault_data_stage1'),
    dict(id='F02', fixture='two-hop', fault='data-once', role='stage2', witness='fault_data_stage2'),
    dict(id='F03', fixture='two-hop', fault='ack-once', role='stage1', witness='fault_tpack'),
    dict(id='F04', fixture='two-hop', fault='taack-once', role='stage2', witness='fault_taack'),
    dict(id='F05', fixture='two-hop', fault='duplicate-once', role='stage2', witness='duplicate_delivery'),
)
NEGATIVES = (
    ('N01','tail','weight-byte','payload byte mismatch'),
    ('N02','two-hop','relay-buffer-byte','payload byte mismatch'),
    ('N03','two-hop','early-relay','relay before target chunk ready'),
    ('N04','slow-relay','early-group','relay before target chunk ready'),
    ('N05','tail','early-final-ready','final ready before full weight coverage'),
    ('N06','two-hop','premature-ready','ready before target completion coverage'),
    ('N07','two-hop','early-wqe','sender completed before target data ready'),
    ('N08','two-hop','duplicate-completion','audit premature/duplicate sender completion'),
    ('N09','two-hop','duplicate-weight','duplicate forwarding'),
)
# The 14 requested coverage categories. Each maps to concrete runtime evidence,
# not merely to a test name, graph possibility, or successful exit status.
COVERAGE = {
    '01_zero_replica': ['zero_replicas'],
    '02_singleton': ['singleton_native'],
    '03_fanout_2_3_4': ['fanout2','fanout3','fanout4'],
    '04_direct_fallback': ['direct_fallback'],
    '05_two_hop_envelopes': ['stage1_envelope','stage2_envelope'],
    '06_multiple_relays_concurrent_experts': ['multiple_relays','concurrent_experts'],
    '07_real_chunk_streaming': ['streaming_physical','groupchunk_all_parents'],
    '08_tail_and_shard_boundaries': ['tail_ranges','nondivisible_shard'],
    '09_expert_chunk_isolation': ['cross_expert_chunk_isolation'],
    '10_mixed_native_envelope_offsets': ['first_unicast_then_merge','envelope_unicast_envelope'],
    '11_native_window_backpressure': ['ta_window_512'],
    '12_lifetime_resources': ['lifetime_groups_gt1024','resource_cleanup'],
    '13_native_recovery_and_idempotence': ['fault_data_stage1','fault_data_stage2','fault_tpack','fault_taack',
                                         'duplicate_delivery','duplicate_ready','completion_reorder','stale_grant'],
    '14_original_four_strategy_parity': ['original_four_strategy_parity'],
}
UNSUPPORTED = [
    'Native TA wire-SSN wrap: not exercised by the fixed ~1058-TA pressure fixture.',
    'Native packet out-of-order injection: reorder_ns changes target completion callbacks only.',
    'Persistent loss/exhaustion: native exhaustion may assert, not graceful recovered cleanup.',
    'Source-envelope loss, lost CBFC credits, Selective/CC and multi-switch reliability.',
]


def matrix():
    fixtures = definitions()
    rows = [dict(id=f'B{i:02d}', kind='positive', fixture=name, strategy=HYBRID,
                 required_witnesses=value['required_witnesses'], options=[],log_level=value['log_level'])
            for i,(name,value) in enumerate(fixtures.items(),1)]
    rows += [dict(id='B11',kind='positive',fixture='two-hop',strategy=HYBRID,
                  required_witnesses=['duplicate_ready'],options=['--fault=duplicate-notify'],log_level='events'),
             dict(id='B12',kind='positive',fixture='two-hop',strategy=HYBRID,
                  required_witnesses=['stale_grant'],options=['--invalidateGrant=1'],log_level='events')]
    for fault in FAULTS:
        rows.append(dict(id=fault['id'],kind='fault',fixture=fault['fixture'],strategy=HYBRID,
            required_witnesses=[fault['witness']], fault=fault['fault'], fault_role=fault['role'],
            options=['--nativeRetrans=1','--networkFault='+fault['fault'],'--networkFaultRole='+fault['role']],log_level='events'))
    for ident,fixture,fault,message in NEGATIVES:
        rows.append(dict(id=ident,kind='negative',fixture=fixture,strategy=HYBRID,
            required_witnesses=[],expected_error=message, options=['--fault='+fault],log_level='events'))
    for fixture in REGRESSION_FIXTURES:
        for mode in OLD_MODES:
            rows.append(dict(id='R-'+fixture+'-'+mode,kind='regression',fixture=fixture,strategy=mode,
                required_witnesses=[],options=[],log_level='summary',executables=['accepted','candidate']))
    return dict(schema_version=SCHEMA,status='DECLARED_NOT_EXECUTED',budget=BUDGET,
        synthetic_only=True,maximum_tokens=max(len(v['planner_input']['mapping']) for v in fixtures.values()),
        native_ta_window=512,fixtures=fixtures,rows=rows,coverage=COVERAGE,
        unsupported=UNSUPPORTED,transition_policy='Require live offset transition evidence across successful rows; otherwise gate INCOMPLETE, never fabricate alignment or PASS.',
        simulator_executions=sum(2 if r['kind']=='regression' else 1 for r in rows),
        accepted_binary_sha256=ACCEPTED_BINARY_SHA256)


def inspect_topology(config, plan, expected):
    """Admit only an actually generated intended graph; no timing results used."""
    groups=config['hybrid_groups']; segment=config['runtime']['segment_bytes']
    roles=Counter(g['graph_role'] for g in groups)
    fanouts=Counter(len(g['members']) for g in groups)
    if 'groups' in expected: require(len(groups)==expected['groups'],'Fixture exact group count absent')
    if 'min_groups' in expected: require(len(groups)>=expected['min_groups'],'Fixture lifetime groups absent')
    if 'fanout' in expected: require(expected['fanout'] in fanouts,'Fixture singleton/fanout absent')
    for key,role in [('direct_fanout','direct-fallback'),('stage1_fanout','stage1'),('stage2_fanout','stage2')]:
        if key in expected: require(any(g['graph_role']==role and len(g['members'])==expected[key] for g in groups),'Fixture '+key+' absent')
    if 'min_stage2_groups' in expected: require(roles['stage2']>=expected['min_stage2_groups'],'Fixture Stage II absent')
    if 'min_experts' in expected: require(len({g['expert'] for g in groups})>=expected['min_experts'],'Fixture multiple experts absent')
    if 'min_relays' in expected: require(len({g['source_physical'] for g in groups if g['graph_role']=='stage2'})>=expected['min_relays'],'Fixture multiple relays absent')
    if expected.get('tail'): require(any(g['bytes']%segment for g in groups),'Fixture TA tail absent')
    if expected.get('shard_tail'):
        p=config['runtime']; cut=(p['matrices']-1)*p['model_dim']*p['ff_dim']*p.get('weight_dtype_bytes',p['dtype_bytes'])
        require(p['weight_size_kind']=='matrix_exact' and cut%p['chunk_bytes'] and any(g['offset']+g['bytes']==cut for g in groups),'Fixture nondivisible shard boundary absent')
    pair_tas=Counter()
    for g in groups:
        for m in g['members']:pair_tas[g['source'],m['target']]+=(g['bytes']+segment-1)//segment
    if 'min_pair_tas' in expected: require(max(pair_tas.values(),default=0)>=expected['min_pair_tas'],'Fixture >512 pair TAs absent')
    return dict(groups=len(groups),roles=dict(roles),fanouts=dict(fanouts),max_pair_tas=max(pair_tas.values(),default=0))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path)
    args=parser.parse_args(); result=matrix();result['matrix_semantic_sha256']=semantic(result)
    if args.out:write(args.out,result)
    else:print(json.dumps(result,indent=2))

if __name__=='__main__':main()
