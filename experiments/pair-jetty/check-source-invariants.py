#!/usr/bin/env python3
"""Supplementary source-parity checks; never a substitute for executed tests."""
from pathlib import Path
import json
H=Path(__file__).resolve().parent
old=(H.parent/'multi-npu-relay/multi-npu-relay.cc').read_text();new=(H/'pair-layer.cc').read_text()
def section(s,start,end):return s[s.index(start):s.index(end)]
checks={
 'compute_duration_and_dependency_functions_unchanged':section(old,'    uint64_t Duration(','    void Ready(')==section(new,'    uint64_t Duration(','    void Ready('),
 'original_tracker_preserved':(H.parent/'no-balancing-layer/nb-tracker.h').read_bytes()==(H.parents[1]/'poc/chunk-relay/tracker.h').read_bytes(),
 'write_payload_builder_unchanged':section(old,'    void Validate(','    void Send(')==section(new,'    void Validate(','    void Send('),
}
print(json.dumps(checks,indent=2));assert all(checks.values())
