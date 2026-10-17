#!/usr/bin/env python3
"""Generate an observer-only app copy. Never edit the baseline or native tree."""
import argparse
import difflib
import re
import hashlib
import json
import pathlib
import shutil

EDITS = []
HERE = pathlib.Path(__file__).resolve().parent
EXPECTED = {
    'pair-layer.cc': 'b111e87f56c219169d1f60e04de8c9d35459365fe42a516f0814c7b9610fdc0e',
    'online-validation.inc': 'e47ea638608e57012662a4f253fc4049c7a403cb69ddd527cc05c084fc0d4016',
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise RuntimeError(f'Expected one source anchor, found {text.count(before)}: {before[:120]!r}')
    EDITS.append((before, after, 1))
    return text.replace(before, after)


def scope(phase, name='qprofScope'):
    return f'qprof::Scope {name}(qprof::Phase::{phase});'


def count(name, amount='1', candidate=False):
    return f'qprof::{"Candidate" if candidate else "Count"}(qprof::Counter::{name}{"" if candidate else ","+amount});'


def unwind(text, edits):
    for before, after, count in reversed(edits):
        if text.count(after) != count:
            raise RuntimeError(f'Cannot erase diagnostic edit exactly: {after[:100]!r}')
        text = text.replace(after, before)
    return text


def simulator_calls(text):
    """Balanced C++ call slices, preserving arguments and lambda bodies exactly."""
    result=[]
    for match in re.finditer(r'Simulator::(?:ScheduleNow|Schedule|Stop|Run|Destroy)\s*\(', text):
        start=match.start();pos=match.end();depth=1;quote=None;escaped=False
        while pos<len(text) and depth:
            char=text[pos]
            if quote:
                if escaped:escaped=False
                elif char=='\\':escaped=True
                elif char==quote:quote=None
            elif char in ('"',"'"):quote=char
            elif text.startswith('//',pos):
                pos=text.find('\n',pos)
                if pos<0:raise RuntimeError('Unclosed simulator call')
            elif text.startswith('/*',pos):
                pos=text.find('*/',pos+2)+1
                if pos==0:raise RuntimeError('Unclosed comment')
            elif char=='(':depth+=1
            elif char==')':depth-=1
            pos+=1
        if depth:raise RuntimeError('Unclosed simulator call')
        result.append(text[start:pos])
    return result


def generate(source, output):
    global EDITS
    EDITS=[]
    source=source.resolve();output=output.resolve()
    if output == source or source in output.parents:
        raise ValueError('The generated copy must be outside baseline source directories')
    observed={name:sha(source/name) for name in EXPECTED}
    if observed != EXPECTED:
        raise RuntimeError(f'Baseline source changed; review anchors and SHA pins before instrumentation: {observed}')
    output.mkdir(parents=True,exist_ok=True)
    app=(source/'pair-layer.cc').read_text()
    audit=(source/'online-validation.inc').read_text()
    # Resolve the original relative include graph without copying or modifying it.
    for name in ('../no-balancing-layer/nb-tracker.h','pair-jetty-manager.h','../direct-weight-forward/weight-distribution.h'):
        app=replace_once(app,f'#include "{name}"',f'#include "{(source/name).resolve()}"')
    app=replace_once(app,'using namespace ns3;','#include "profile-runtime.h"\nusing namespace ns3;')
    app=replace_once(app,'class Layer {\npublic:', 'class Layer {\npublic:\n    qprof::LayerLifetime qprofLifetime_;\n    ~Layer(){qprof::ClearObserver();qprofLifetime_.Begin();}')
    for signature,phase in [
        ('void Read(const std::string& path){','Read'),
        ('void Topology(const std::string& out){','Topology'),
        ('void Validate(uint32_t task,uint64_t off,const std::vector<uint8_t>& data){','Validate'),
        ('void Send(uint32_t task){','Send'),
        ('void Ready(uint32_t task){','Ready'),
        ('void WritePayloads(const std::string& out){','WritePayloads'),
    ]:
        app=replace_once(app,signature,signature+scope(phase))
    app=replace_once(app,'transfers.push_back(std::move(x));', 'transfers.push_back(std::move(x));'+count('TransfersCreated')+count('TransferPayloadAllocated','size'))
    app=replace_once(app,'        if(strategy==0)edges=', '        {'+scope('ReadEdges')+'\n        if(strategy==0)edges=')
    app=replace_once(app,'        Require(edges.size()==predictedEdges', '        }\n        Require(edges.size()==predictedEdges')
    app=replace_once(app,'        for(uint32_t stage=0;stage<2;++stage)', '        {'+scope('ReadTransfers')+'\n        for(uint32_t stage=0;stage<2;++stage)')
    app=replace_once(app,'        dependents.resize(transfers.size());', '        }\n        {'+scope('ReadDependencies')+'\n        dependents.resize(transfers.size());')
    app=replace_once(app,'            auto scope=edges[task-2*assignments.size()].sourceDependency;', '            '+count('DependencyReplicaTasks')+'\n            auto scope=edges[task-2*assignments.size()].sourceDependency;')
    app=replace_once(app,'                auto& y=transfers[parent];', '                '+count('DependencyCandidates',candidate=True)+'\n                auto& y=transfers[parent];')
    app=replace_once(app,'                x.dependencies.push_back(parent);', '                '+count('DependencyEdges')+'\n                x.dependencies.push_back(parent);')
    app=replace_once(app,'        weightData.resize(np);weightCoverage.resize(np);', '        }\n        {'+scope('ReadWeights')+'\n        weightData.resize(np);weightCoverage.resize(np);')
    app=replace_once(app,'weightData[i].resize(weightBytes);', 'weightData[i].resize(weightBytes);'+count('ReplicaPayloadAllocated','weightBytes'))
    app=replace_once(app,'        if(!balanced)Require(!pendingWeights', '        }\n        qprof::SetModel(assignments.size(),transfers.size(),n,physical.size());\n        if(!balanced)Require(!pendingWeights')
    app=replace_once(app,'if(x.stage==2)for(auto parent:x.dependencies)Require(transfers[parent].ready,"relay before target chunk ready (including group)");',
        'if(x.stage==2)for(auto parent:x.dependencies){'+count('SendDependencyChecks')+'Require(transfers[parent].ready,"relay before target chunk ready (including group)");}')
    app=replace_once(app,'        if(x.stage==2&&P(x.sourcePhysical).replica){\n            TE("relay_buffer_read"',
        '        '+count('SendPayloadBytes','x.bytes')+'\n        if(x.stage==2&&P(x.sourcePhysical).replica){\n            TE("relay_buffer_read"')
    app=replace_once(app,'}verificationNs+=std::chrono::duration_cast', '}'+count('ValidatePayloadBytes','data.size()')+'verificationNs+=std::chrono::duration_cast')
    original='[this](auto p){return transfers[p].ready;}'
    if app.count(original)!=2:raise RuntimeError('Expected exactly two Ready dependency predicates')
    replacement='[this](auto p){'+count('ReadyDependencyPredicates')+'return transfers[p].ready;}'
    EDITS.append((original,replacement,2))
    app=app.replace(original,replacement)
    app=replace_once(app,'Require(fn->SubmitWqe(wqe,x.jettyId).status==UbWqeSubmissionStatus::ACCEPTED,\"WQE rejected\");',
        'Require(fn->SubmitWqe(wqe,x.jettyId).status==UbWqeSubmissionStatus::ACCEPTED,\"WQE rejected\");'+count('RemoteWqesSubmitted'))
    app=replace_once(app,'    void Run(const std::string& input,const std::string& out){',
        '    void Run(const std::string& input,const std::string& out){\n        qprof::SetObserver(this,[](void* pointer){const auto& x=*static_cast<Layer*>(pointer);qprof::Progress(x.assignments.size(),x.transfers.size(),x.remoteCount,x.taCount,x.senderCount,x.receivedTokens,x.pendingWeights,x.txPackets,x.rxPackets,x.txBytes,x.rxBytes);});')
    app=replace_once(app,'Simulator::Run();', '{'+scope('SimulatorRun')+'qprof::SimulatorStarted();Simulator::Run();qprof::FreezeSimulator();}')
    app=replace_once(app,'admissions.close();log.close();UbUtils::Get()->Destroy();traceOn=false;Simulator::Destroy();',
        'admissions.close();log.close();{'+scope('UbDestroy')+'UbUtils::Get()->Destroy();}traceOn=false;{'+scope('SimulatorDestroy')+'Simulator::Destroy();}')
    app=replace_once(app,'int main(int argc,char** argv){', 'int main(int argc,char** argv){qprof::Session qprofSession;')
    app=replace_once(app,'layer.Run(input,out);}catch', 'layer.Run(input,out);qprof::Complete();}catch')
    app=replace_once(app,'catch(const std::exception& ex){', 'catch(const std::exception& ex){qprof::Failed();')
    app_edits=EDITS
    EDITS=[]
    for signature,phase in [
        ('void InitAudit(){','InitAudit'),
        ('void Audit(const std::string& name,int stage,int id,int node,uint64_t off,uint64_t len,int task){','Audit'),
        ('void FinalAudit(){','FinalAudit'),
        ('void WriteSummary(const std::string& out){','WriteSummary'),
    ]:
        audit=replace_once(audit,signature,signature+scope(phase))
    audit=replace_once(audit,'        Require(now>=lastAuditTime', '        '+count('AuditEvents')+'\n        Require(now>=lastAuditTime')
    audit=replace_once(audit,'else for(auto parent:x.dependencies){Require(taskAudit[parent].ready',
        'else for(auto parent:x.dependencies){'+count('AuditSendDependencyChecks')+'Require(taskAudit[parent].ready')
    audit=replace_once(audit,'if(name=="weights_end"){uint64_t end=', 'if(name=="weights_end"){'+scope('AuditWeightsEndScan','qprofScan')+'uint64_t end=')
    audit=replace_once(audit,'for(auto& p:physical)if(p.replica){auto key=',
        'for(auto& p:physical)if((qprof::Candidate(qprof::Counter::AuditWeightsEndCandidates),p.replica)){auto key=')
    audit=replace_once(audit,'if(name=="weight_ready"){auto& p=',
        'if(name=="weight_ready"){'+scope('AuditWeightScan','qprofScan')+count('AuditWeightEvents')+'auto& p=')
    audit=replace_once(audit,'i<transfers.size();++i)if(transfers[i].physical==uint32_t(id)){Require',
        'i<transfers.size();++i)if((qprof::Candidate(qprof::Counter::AuditWeightCandidates),transfers[i].physical==uint32_t(id))){'+count('AuditWeightMatches')+'Require')
    audit=replace_once(audit,'if(name=="group_chunk_ready"){',
        'if(name=="group_chunk_ready"){'+scope('AuditGroupScan','qprofScan')+count('AuditGroupEvents'))
    audit=replace_once(audit,'for(size_t i=2*assignments.size();i<transfers.size();++i){auto& x=',
        'for(size_t i=2*assignments.size();i<transfers.size();++i){'+count('AuditGroupCandidates',candidate=True)+'auto& x=')
    audit=replace_once(audit,'x.bytes==len){Require(taskAudit[i].ready,"audit premature group")',
        'x.bytes==len){'+count('AuditGroupMatches')+'Require(taskAudit[i].ready,"audit premature group")')
    audit=replace_once(audit,'            if(x.stage==1)combineHash=',
        '            '+count('FinalTaskPayloadBytes','x.data.size()')+'\n            if(x.stage==1)combineHash=')
    audit=replace_once(audit,'if(x.stage==2&&!x.dependencies.empty())for(size_t i=0;i<x.data.size();++i)Require(x.data[i]==weightData[pIndex.at(x.sourcePhysical)][x.offset+i],"audit relay final buffer provenance");',
        'if(x.stage==2&&!x.dependencies.empty()){for(size_t i=0;i<x.data.size();++i)Require(x.data[i]==weightData[pIndex.at(x.sourcePhysical)][x.offset+i],"audit relay final buffer provenance");'+count('FinalRelayPayloadBytes','x.data.size()')+'}qprof::Checkpoint();')
    audit=replace_once(audit,'for(size_t i=0;i<physical.size();++i)if(physical[i].replica)for(uint32_t off=0;off<weightBytes;++off)Require(weightData[i][off]==WeightByte(physical[i].id,off),"audit final weight corruption");',
        'for(size_t i=0;i<physical.size();++i)if(physical[i].replica){for(uint32_t off=0;off<weightBytes;++off)Require(weightData[i][off]==WeightByte(physical[i].id,off),"audit final weight corruption");'+count('FinalReplicaPayloadBytes','weightBytes')+'qprof::Checkpoint();}')
    audit_edits=EDITS
    original_app=(source/'pair-layer.cc').read_text()
    original_audit=(source/'online-validation.inc').read_text()
    if unwind(app,app_edits)!=original_app or unwind(audit,audit_edits)!=original_audit:
        raise RuntimeError('Diagnostic erasure did not reproduce pinned baseline bytes')
    original_calls=simulator_calls(original_app)
    if simulator_calls(app)!=original_calls:
        raise RuntimeError('Simulator control call arguments, bodies, order or cardinality changed')
    proof={
        'status':'PASS','baseline_sha256':observed,
        'observer_erasure_roundtrip_byte_exact':True,
        'simulator_control_calls_byte_exact_and_same_order':True,
        'simulator_control_calls_checked':len(original_calls),
        'signal_handler_body':'stopSignal=signal;',
        'simulated_checkpoint_events_added':0,
        'note':'Static proof of transformation scope. Runtime parity remains a separate required gate.'}
    (output/'instrumentation-source-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    patch=''.join(difflib.unified_diff(original_app.splitlines(keepends=True),app.splitlines(keepends=True),fromfile='baseline/pair-layer.cc',tofile='instrumented/pair-layer.cc'))
    patch+=''.join(difflib.unified_diff(original_audit.splitlines(keepends=True),audit.splitlines(keepends=True),fromfile='baseline/online-validation.inc',tofile='instrumented/online-validation.inc'))
    (output/'application-instrumentation.patch').write_text(patch)
    (output/'pair-layer.cc').write_text(app)
    (output/'online-validation.inc').write_text(audit)
    shutil.copyfile(HERE/'profile-runtime.h',output/'profile-runtime.h')
    manifest={
        'schema':1,'scope':'diagnostic-only application copy; original application and native sources unchanged',
        'source_directory':str(source),'output_directory':str(output),
        'baseline_sha256':observed,'generated_sha256':{name:sha(output/name) for name in ['pair-layer.cc','online-validation.inc','profile-runtime.h']},
        'generator_sha256':sha(pathlib.Path(__file__)),
        'patch_sha256':sha(output/'application-instrumentation.patch'),
        'static_proof':proof,
        'compile_flags':['-std=c++20','-O3','-g'],
        'simulation_mutations':'none; no schedule/stop calls added, removed or reordered',
        'verification':'generation only; native compile and runtime parity must be run separately',
    }
    (output/'generation-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if {name:sha(source/name) for name in EXPECTED} != observed:raise RuntimeError('Baseline changed during generation')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=pathlib.Path,default=HERE.parent/'pair-jetty')
    parser.add_argument('--out',type=pathlib.Path,required=True)
    args=parser.parse_args()
    generate(args.source,args.out)
