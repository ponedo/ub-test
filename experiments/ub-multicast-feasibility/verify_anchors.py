#!/usr/bin/env python3
"""Check selected concrete source anchors; not a semantic/protocol proof."""
import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--native',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args()
anchors=[
('src/unified-bus/model/ub-switch.cc',973,1005,'ForwardDataPacket'),
('src/unified-bus/model/ub-switch.cc',449,478,'ForwardDataPacketAfterAdmission'),
('src/unified-bus/model/ub-switch.cc',819,881,'SinkTpDataPacket'),
('src/unified-bus/model/ub-switch-allocator.cc',652,710,'AllocateNextPacket'),
('src/unified-bus/model/ub-port.cc',790,842,'TransmitPacket'),
('src/unified-bus/model/ub-link.cc',174,203,'TransmitStart'),
('src/unified-bus/model/protocol/ub-cbfc.cc',147,166,'OnIngressReleased'),
('src/unified-bus/model/protocol/ub-routing-process.cc',450,532,'GetOutPortInternal'),
('src/unified-bus/model/ub-transport-channel-manager.cc',238,299,'ResolveInboundTp'),
('src/unified-bus/model/protocol/ub-function.cc',155,241,'SubmitWqe'),
('src/unified-bus/model/protocol/ub-function.cc',1058,1072,'CanAcceptWqe'),
('src/unified-bus/model/protocol/ub-function.cc',1629,1641,'IsWqeCompleted'),
('src/unified-bus/model/protocol/ub-transaction.cc',1859,1918,'RecordSegmentSuccess'),
('src/unified-bus/model/protocol/ub-transaction.cc',2114,2177,'ProcessInboundTaResponse'),
('src/unified-bus/model/protocol/ub-transport.cc',1043,1067,'BuildRtpDataPacket'),
('src/unified-bus/model/protocol/ub-transport.cc',1343,1360,'ShouldCompleteOnTpAck'),
('src/unified-bus/model/protocol/ub-retrans.cc',1201,1225,'OnTimeout'),
('src/network/model/packet.cc',120,125,'Packet::Copy'),
('src/network/model/packet.h',849,852,'GetSize'),
('src/core/model/assert.h',39,104,'NS3_ASSERT_ENABLE')]
rows=[]
for path,start,end,needle in anchors:
 lines=(a.native/path).read_text().splitlines();ok=end<=len(lines) and needle in '\n'.join(lines[start-1:end]);rows.append(dict(path=path,start=start,end=end,needle=needle,passed=ok))
result=dict(kind='source-anchor text checks; not simulation tests',checked=len(rows),passed=all(x['passed'] for x in rows),anchors=rows)
a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checked':len(rows),'passed':result['passed']}))
if not result['passed']:raise SystemExit(1)
