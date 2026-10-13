// SPDX-License-Identifier: Apache-2.0
// Testbench ONLY. SC_doorbell and SC_jsched below are emitted from upstream
// .clnp by the official OpenClickNP compiler; no scheduler is implemented here.
#include <systemc.h>
#include "openclicknp/sc_runtime.hpp"
#include "openurma/ub_flit.hpp"
#include <fstream>
#include <iostream>
#include <map>
#include <vector>
#include <algorithm>
#include <stdexcept>
namespace openclicknp {
inline std::ostream& operator<<(std::ostream& o,const flit_t&){return o<<"flit";}
inline bool operator==(const flit_t&a,const flit_t&b){return a.raw==b.raw;}
}
inline void sc_trace(sc_core::sc_trace_file*,const openclicknp::flit_t&,const std::string&){}
#include "topology_no_main.cpp"
using F=openclicknp::flit_t;
static uint64_t nowps(){return sc_time_stamp().value();}
static void check(bool x,const char*msg){if(!x)throw std::runtime_error(msg);}
struct Request {
    unsigned id,jetty,sequence,length,opcode;bool fence;
    std::vector<F> flits;
    uint64_t submit=0,ext_submit=0,dispatch=0,complete=0;
    unsigned offered=0,received=0;
};
struct ProbeFifo:sc_fifo<F>{
    std::function<void(const char*,const F&)> trace;
    ProbeFifo(const char*n,int depth):sc_fifo<F>(n,depth){}
    void write(const F&f)override{trace("offer",f);sc_fifo<F>::write(f);trace("accept",f);}
};
SC_MODULE(Bench){
    sc_fifo<F> source_fifo,door_fifo,notify_fifo;
    ProbeFifo output_fifo;
    SC_doorbell door;
    SC_jsched scheduler;
    std::vector<Request> requests;std::map<unsigned,unsigned> by_id;
    std::ofstream events,queues;
    std::string mode,scenario,ordering;
    unsigned completed=0,period=4;uint64_t event_seq=0;bool finished=false;
    SC_HAS_PROCESS(Bench);
    Bench(sc_module_name n,const std::string&m,const std::string&s,const std::string&o,const std::string&prefix)
      :sc_module(n),source_fifo("source_fifo",8),door_fifo("door_fifo",8),notify_fifo("notify_fifo",8),output_fifo("output_fifo",1),
       door("door"),scheduler("scheduler"),events(prefix+".events.csv"),queues(prefix+".queues.csv"),mode(m),scenario(s),ordering(o){
        check(bool(events)&&bool(queues),"output open failed");
#ifndef OPENURMA_NATIVE
        scheduler._state.use_drr=(mode=="drr");scheduler._state.quantum_bytes=256;
#else
        check(mode=="rr","native upstream supports RR only");
#endif
        door.in_1(source_fifo);door.out_1(door_fifo);scheduler.in_1(door_fifo);scheduler.in_2(notify_fifo);scheduler.out_1(output_fifo);
        events<<"event_seq,delta,time_ps,event,wr_id,jetty,flit_index,payload_bytes,raw_hex\n";
        queues<<"time_ps,q0,q1,q2,active_ini,outstanding0\n";
        build();output_fifo.trace=[&](const char*event,const F&f){
            auto&r=row(f);unsigned index=index_of(f);
            if(std::string(event)=="offer"){
                check(index==r.offered++,"duplicate/reordered output offer");
                if(f.sop())r.dispatch=nowps();
            }
            log(event,r,index,&f);
        };
        SC_THREAD(feed);SC_THREAD(sink);SC_THREAD(notify);SC_THREAD(sample);SC_THREAD(watchdog);
    }
    unsigned index_of(const F&f){return unsigned(f.raw[50])|(unsigned(f.raw[51])<<8);}
    Request&row(const F&f){return requests.at(by_id.at(f.slot_id()));}
    void log(const char*event,Request&r,unsigned index,const F*f=nullptr){
        events<<event_seq++<<','<<sc_delta_count()<<','<<nowps()<<','<<event<<','<<r.id<<','<<r.jetty<<','<<index<<',';
        unsigned bytes=f && index>=2 && r.opcode==openurma::TAOP_WRITE ? 32-f->padbytes():0;events<<bytes<<',';
        const char*hex="0123456789abcdef";
        if(f)for(auto byte:f->raw)events<<hex[byte>>4]<<hex[byte&15];
        events<<'\n';
    }
    void add(unsigned id,unsigned j,unsigned seq,unsigned len,unsigned opcode=openurma::TAOP_WRITE,bool fence=false,bool single=false){
        Request r{id,j,seq,len,opcode,fence,{}};
        openurma::ub_meta m{};m.set_dcna(0xabc123);m.set_scna(1);m.set_valid(true);m.set_ta_opcode(opcode);
        m.set_svc_mode(openurma::SVC_ROL);m.set_ini_rc_id(j);m.set_ini_tassn(id);m.set_fence(fence);m.set_last_pkt(true);
        m.f.set_sop(true);m.f.set_eop(single);r.flits.push_back(m.f);
        if(!single){
            openurma::ub_ext e{};e.set_address(uint64_t(id)*8192);e.set_length(len);e.set_token_id(0x55);e.f.set_eop(len==0);r.flits.push_back(e.f);
            for(unsigned offset=0;offset<len;offset+=32){F f{};unsigned count=std::min(32u,len-offset);
                for(unsigned k=0;k<count;++k)f.raw[k]=uint8_t(id*37+(offset+k)*13+7);
                f.set_padbytes(32-count);f.set_eop(offset+count==len);r.flits.push_back(f);
            }
        }
        for(unsigned i=0;i<r.flits.size();++i){r.flits[i].set_slot_id(id);r.flits[i].raw[50]=i&255;r.flits[i].raw[51]=i>>8;}
        by_id[id]=requests.size();requests.push_back(std::move(r));
    }
    void build(){
        if(scenario=="fence"){
            add(0,0,0,0,openurma::TAOP_READ,false,true);add(1,0,1,0,openurma::TAOP_ATOMIC_CAS,false,true);
            add(2,0,2,64,openurma::TAOP_WRITE,true);add(3,1,0,64);return;
        }
        if(scenario=="overflow"){
            add(0,0,0,0,openurma::TAOP_READ,false,true);
            for(unsigned i=1;i<=40;++i)add(i,0,i,0,openurma::TAOP_WRITE,true,true);return;
        }
        if(scenario=="large"){add(0,0,0,4097);add(1,1,0,4097);return;}
        if(scenario=="delayed_ext"){add(0,0,0,64);add(1,1,0,64);return;}
        unsigned count=scenario=="smoke"?2:96;
        for(unsigned seq=0;seq<count;++seq)for(unsigned k=0;k<3;++k){unsigned j=ordering=="reverse"?2-k:k;
            add(seq*3+j,j,seq,scenario=="equal"||scenario=="smoke"?256:(j==0?64:j==1?256:1024));
        }
    }
    void feed(){
        wait(10,SC_NS);
        for(auto&r:requests)log("ready",r,0);
        for(auto&r:requests){
            for(unsigned i=0;i<r.flits.size();++i){
                if(scenario=="delayed_ext" && r.id==0 && i==1)wait(100,SC_NS);
                source_fifo.write(r.flits[i]);
                if(i==0)r.submit=nowps();if(i==1)r.ext_submit=nowps();
                log("submit_flit",r,i,&r.flits[i]);
            }
        }
    }
    void sink(){
        if(scenario=="stall")wait(500,SC_NS);
        int active=-1;std::map<unsigned,unsigned> next;
        while(true){
            F f=output_fifo.read();auto&r=row(f);unsigned index=index_of(f);
            check(index==r.received,"loss, duplicate, or flit reorder");check(f.raw==r.flits.at(index).raw,"payload/header corruption");
            if(f.sop()){check(active==-1,"interleaved WRs");check(r.sequence==next[r.jetty]++,"per-Jetty WR reorder");active=r.id;}
            check(active==int(r.id),"packet owner changed");++r.received;log("receive",r,index,&f);
            if(f.eop()){
                check(r.received==r.flits.size(),"early EOP");r.complete=nowps();active=-1;log("component_complete",r,index);++completed;
                if(completed==requests.size()){finished=true;wait(2,SC_NS);sc_stop();return;}
            }
            wait(period,SC_NS);
        }
    }
    void notify(){
        if(scenario!="fence"&&scenario!="overflow")return;
        wait(scenario=="fence"?200:1000,SC_NS);
        F f{};f.set(0,0);f.set_sop(true);f.set_eop(true);notify_fifo.write(f);log("read_atomic_notify",requests[0],0);
        if(scenario=="fence"){wait(200,SC_NS);notify_fifo.write(f);log("read_atomic_notify",requests[1],0);}
    }
    void sample(){while(true){wait(1,SC_NS);wait(SC_ZERO_TIME);
        queues<<nowps();for(unsigned i=0;i<3;++i){auto&q=scheduler._state.q[i];queues<<','<<((q.tail+32-q.head)%32);}
        queues<<','<<scheduler._state.drain_active_ini<<','<<scheduler._state.q[0].outstanding_read_atomic<<'\n';
    }}
    void watchdog(){wait(100000,SC_NS);sc_stop();}
    void validate(const std::string&prefix){
        std::ofstream wr(prefix+".wr.csv");wr<<"wr_id,jetty,sequence,payload_bytes,flits,submit_ps,extension_submit_ps,dispatch_ps,component_complete_ps,received_flits\n";
        for(auto&r:requests)wr<<r.id<<','<<r.jetty<<','<<r.sequence<<','<<r.length<<','<<r.flits.size()<<','<<r.submit<<','<<r.ext_submit<<','<<r.dispatch<<','<<r.complete<<','<<r.received<<'\n';
        std::cout<<"completed="<<completed<<" expected="<<requests.size()<<" (component output EOP, NOT protocol CQ/ACK)\n";
#ifndef OPENURMA_NATIVE
        std::cout<<"input_full_cycles="<<scheduler._state.input_full_cycles<<'\n';
        if(scenario=="overflow")check(scheduler._state.input_full_cycles>0,"overflow guard not exercised");
#endif
        check(finished && completed==requests.size(),"missing WRs / deadlock");
        if(scenario=="fence"){
            check(requests[2].dispatch>=400000,"Fence escaped outstanding Read/Atomic");
            check(requests[3].dispatch<200000,"independent Initiator blocked by Fence");
        }
        if(scenario=="delayed_ext"&&mode=="drr")check(requests[0].dispatch>=requests[0].ext_submit,"DRR selected before cost available");
        for(unsigned i=0;i<16;++i)check(scheduler._state.q[i].head==scheduler._state.q[i].tail && scheduler._state.q[i].outstanding_read_atomic==0,"state not drained");
        std::cout<<"PASS: real generated SC_jsched; all flits byte-exact, FIFO, packet contiguity, completion and state drain\n";
    }
};
int sc_main(int argc,char**argv){try{
    check(argc==5,"usage: component rr|drr scenario forward|reverse PREFIX");
    sc_set_time_resolution(1,SC_PS);std::string mode=argv[1],scenario=argv[2],order=argv[3];
    check(mode=="rr"||mode=="drr","bad policy");check(order=="forward"||order=="reverse","bad order");
    check(scenario=="equal"||scenario=="mixed"||scenario=="smoke"||scenario=="fence"||scenario=="overflow"||scenario=="large"||scenario=="stall"||scenario=="delayed_ext","bad scenario");
    Bench b("bench",mode,scenario,order,argv[4]);sc_start();b.validate(argv[4]);return 0;
}catch(const std::exception&e){std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}}
