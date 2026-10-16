#!/usr/bin/env python3
import json,re,subprocess,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent; REPO=HERE.parents[1]; N=Path('/workspace/prefill-cpu-native'); names={}
def inject(path,pattern,name,expected=1):
 text=path.read_text();id=len(names);text,n=re.subn(pattern,lambda m:m[0]+f'\nCpuScope cpuScope{id}({id});\n',text)
 if n!=expected:raise RuntimeError((path,name,n,expected))
 path.write_text(text);names[id]=name
def fn(path,name,expected=1):inject(path,re.escape(name)+r'\([^;{}]*\)[^;{}]*\{',name,expected)
paths=['src/unified-bus/model/protocol/ub-function.cc','src/unified-bus/model/protocol/ub-function.h','src/unified-bus/model/protocol/ub-transaction.cc','src/unified-bus/model/ub-utils.cc','src/unified-bus/model/ub-port.cc','src/unified-bus/model/protocol/ub-transport.cc']
for p in paths:(N/p).write_bytes(subprocess.check_output(['git','-C',str(N),'show','HEAD:'+p]))
app=N/'scratch/multi-npu-relay.cc';shutil.copyfile(REPO/'experiments/multi-npu-relay/multi-npu-relay.cc',app)
for name in ['Read','WriteArtifacts','Topology','Pair','Init','Validate','Send','Event','WritePayloads']:
 inject(app,r'\bvoid '+name+r'\([^;{}]*\)[^;{}]*\{','app.'+name)
inject(app,r'int main\(int argc,char\*\* argv\)\{','app.main')
for text,name in [('Simulator::Run();','phase.SimulatorRun'),('UbUtils::Get()->Destroy();traceOn=false;Simulator::Destroy();','phase.cleanup')]:
 id=len(names);s=app.read_text();assert s.count(text)==1;s=s.replace(text,'{CpuScope cpuScope'+str(id)+'('+str(id)+');'+text+'}');app.write_text(s);names[id]=name
for file,funcs in [(paths[0],['UbFunction::CreateJetty','UbFunction::SubmitWqe','UbJettyManager::ResolveWqeLifecycleLocalId','UbJettyManager::RegisterJetty','UbJettyManager::RegisterWqe','UbJettyManager::GetJetty','UbJettyManager::IsJettyExists','UbJetty::Init']),(paths[2],['UbTransaction::ExecuteInboundTransaction','UbTransaction::ProcessWqeSegmentComplete','UbTransaction::AddWqe','UbTransaction::TriggerScheduleWqeSegment']),(paths[3],['UbUtils::AppendTraceLine','UbUtils::CommitTraceChunk','UbUtils::FlushTraceFile']),(paths[4],['UbPort::DispatchReceive']),(paths[5],['UbTransportChannel::ParseReceivedDataPacket','UbTransportChannel::HandleReceivedAckOrSack'])]:
 for name in funcs:fn(N/file,name,2 if name=='UbFunction::CreateJetty' else 1)
inject(N/paths[1],r'\bvoid ResetSsnAckBitset\([^;{}]*\)[^;{}]*\{','Jetty.AckWindow.ResizeReset')
(HERE/'evidence/scopes.json').write_text(json.dumps(names,indent=2)+'\n')
(HERE/'evidence/native-instrumentation.patch').write_bytes(subprocess.check_output(['git','-C',str(N),'diff']))
r=subprocess.run(['diff','-u',str(REPO/'experiments/multi-npu-relay/multi-npu-relay.cc'),str(app)],capture_output=True);(HERE/'evidence/app-instrumentation.patch').write_bytes(r.stdout)
