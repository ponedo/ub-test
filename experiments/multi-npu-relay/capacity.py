"""Allocation-free weight task count bound; mirrors existing relay eligibility only."""
def weight_task_count(physical, strategy, weight_bytes, options, shard_cut):
 from collections import Counter
 counts=Counter(x['expert'] for x in physical if x['kind']=='replica')
 total=0
 for count in counts.values():
  nr=0
  if count>1:
   while (nr+1)**2<=count:nr+=1
   nr=min(nr,options['relay_max_relays'],count-1)
  relay=nr and (options['force_relay'] or (count>=options['relay_min_replicas'] and count-max(nr,(count-nr+nr-1)//nr)>=options['relay_min_fanout_gain']))
  pieces=1
  if strategy=='chunk-streaming' and relay:
   sizes=[shard_cut,weight_bytes-shard_cut] if shard_cut else [weight_bytes]
   pieces=sum((size+options['chunk_bytes']-1)//options['chunk_bytes'] for size in sizes)
  total+=count*pieces
 return total
