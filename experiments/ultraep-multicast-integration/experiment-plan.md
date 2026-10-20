# Plan
Claim: same accepted planner and real L37/N2048 assignment can reduce expert weight distribution and layer time via v2 shared first-send payload.
Controls: identical pair endpoints,model,weight size,trace,compute,token transfers,single-switch links/queues/CBFC and validators. NoBal intentionally has no planner/reroute/replica overhead. Direct/Chunk/v2 share all semantic plan fields, excluding measured cpu_wall_ns only.
Treatment: weight distribution strategy4 using v2. Prediction conditional: source traffic shrinks forfanout>1,downstream remains native WRITE; layer benefit depends on global ready critical path. No assumed speedup or result substitution.
Stage A: bounded synthetic EP4/8 cases no replicas,singleton,multi-target,concurrent experts and overlapping receivers; compare validated outputs,receiver gating,independent WQE completion and resources. Fault negatives/retry smoke after initial positive cases.
Stage B: only after A,prepare exact private L37/N2048 real235B input using prior source manifest/counts/raw-prefix; auditcapacity; sequentialNoBal,Direct,Chunk,v2 on unified source/native/config. Record simulator timing separately from host timing. Stop for guard/fairness/validation failures; no automatic resource expansion.
Stage C: only actual L37 results,aggregatefanout/header/source andswitch bytes,per-expert ready andlastcriticalexpert; no extra sizes/layers.
Artifacts: source,patch,preparation/guardedrun/independentcheck scripts,case specs,CSV/charts/report,source/input hash provenance,remoteverification. Rawrouting/pertoken/payload/Debug private.
