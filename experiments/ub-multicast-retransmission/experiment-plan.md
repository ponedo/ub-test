# Experiment plan
Claim: shared first-send envelope can reuse existing per-target GBN retry with unicast replay.
Control: v2 with native GBN enabled, 12KiB per target,1024B TA,100Gbps20ns single switch,three targets,CBFC enabled,CC unchanged disabled as prior validated scope.
Treatments: isolated B last request PSN11 data drop,duplicate delivery,last TPACK drop,last TA response drop,persistent data loss,disabled-retrans comparison. Last segment isolates exactly one outstanding request rather than claiming GBN is selective.
Prediction: one loss -> native timeout -> unicast to B only; duplicate -> no repeat target execution; feedback loss -> correct direction replay; persistent -> no group success and assertion or bounded incomplete result.
Falsification: no native retry, retry gets envelope, C/D repeated data, wrong payload/identity, repeated or premature completion, unbounded/credit/accounting fault. Report every negative and limitation.
Evidence: physical TX/RX and queue enqueue traces; source native construction; TP PSN/window/descriptors/timer,TA SSN,WQE/group events,actual payload; bounded summaries and required Events only.
Checkpoint: audit before edit; canary baseline then single loss; unknown native core defect pauses dependent implementation; no new reliability code. Artifacts in this directory; private raw payload/logs outside project.
