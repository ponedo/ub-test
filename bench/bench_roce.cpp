#include <nano/roce/tx.h>
#include <nano/roce/rx.h>
#include <nano/eth_link.h>
#include <nano/eval/latency_model.h>
#include <iostream>
#include <iomanip>

SC_MODULE(Sn) { sc_fifo_in<Flit> i; sc_time t; bool h=false;
    SC_HAS_PROCESS(Sn); Sn(sc_module_name n):sc_module(n){SC_THREAD(r);}
    void r(){i.read();t=sc_time_stamp();h=true;} };

int sc_main(int,char*[]) {
    std::cout<<"=== RoCE RC ==="<<std::endl;

    // ===== Node A =====
    sc_fifo<Flit> a_f1("a_f1"),a_f2("a_f2"),a_f3("a_f3"),a_f4("a_f4"),a_wtx("a_wtx");
    sc_fifo<Flit> a_wrx("a_wrx"),a_dco("a_dco");

    Doorbell   a_dr("a_dr"); QpTx a_qp("a_qp",1,2);
    BthBuilder a_bb("a_bb"); RoceEncap a_re("a_re");
    a_dr.wr_in .bind(a_f1);  a_dr.wr_out.bind(a_f2);
    a_qp.in    .bind(a_f2);  a_qp.out   .bind(a_f3);
    a_bb.in    .bind(a_f3);  a_bb.out   .bind(a_f4);
    a_re.in    .bind(a_f4);  a_re.out   .bind(a_wtx);

    RoceDecap a_dc("a_dc"); Sn a_sn("a_sn");
    a_dc.in .bind(a_wrx);  a_dc.out .bind(a_dco);
    a_sn.i.bind(a_dco);

    // ===== Node B =====
    sc_fifo<Flit> b_wrx("b_wrx"),b_f1("b_f1"),b_f2("b_f2"),b_data("b_data");
    sc_fifo<Flit> b_ar("b_ar"),b_rd("b_rd");
    sc_fifo<Flit> b_wd("b_wd"),b_sd("b_sd"),b_ad("b_ad");
    sc_fifo<Flit> b_mresp("b_mresp"),b_mw("b_mw");
    sc_fifo<Flit> b_ack("b_ack"),b_tx1("b_tx1"),b_tx2("b_tx2"),b_tx3("b_tx3"),b_wtx("b_wtx");

    RoceDecap    b_dc("b_dc");   QpRx       b_qp("b_qp"); BthParser    b_bp("b_bp");
    Dispatch     b_dp("b_dp");   MemoryModel b_mem("b_mem");
    QpTx         b_aqp("b_aqp",2,1); BthBuilder b_ab("b_ab"); RoceEncap b_ae("b_ae");

    b_dc.in .bind(b_wrx);  b_dc.out .bind(b_f1);
    b_qp.in .bind(b_f1);   b_qp.out .bind(b_f2);
    b_bp.in .bind(b_f2);   b_bp.data_out.bind(b_data);
    b_bp.ack_out   .bind(b_ar);
    b_dp.in        .bind(b_data);
    b_dp.read_req  .bind(b_rd);
    b_dp.write_req .bind(b_wd);
    b_dp.send_req  .bind(b_sd);
    b_dp.atomic_req.bind(b_ad);
    b_mem.read_in  .bind(b_rd);
    b_mem.read_resp.bind(b_mresp);
    b_mem.write_in .bind(b_wd);
    b_mem.write_done.bind(b_mw);

    b_aqp.in .bind(b_mresp); b_aqp.out .bind(b_tx1);
    b_ab.in  .bind(b_tx1);   b_ab.out  .bind(b_tx2);
    b_ae.in  .bind(b_tx2);   b_ae.out  .bind(b_wtx);

    // ===== EtherLink =====
    EtherLink link("link", sc_time(100, SC_NS));
    link.a_to_link.bind(a_wtx);
    link.link_to_b.bind(b_wrx);
    link.b_to_link.bind(b_wtx);
    link.link_to_a.bind(a_wrx);

    // ===== Send READ =====
    sc_time t0=sc_time_stamp();
    Flit f=Flit::make_valid(); f.ta_opcode=6; f.mem_addr=0x1000; f.mem_len=8;
    a_f1.write(f);
    sc_start(10000,SC_NS);
    double ns=a_sn.h?(a_sn.t-t0).to_seconds()*1e9:99999;

    std::cout<<"  READ 8B @100ns link: "<<std::fixed<<std::setprecision(1)
             <<ns<<" ns  ("<<(uint64_t)nano::eval::ns_to_cycles(ns)<<" cyc)"<<std::endl
             <<"=== OK ==="<<std::endl;
    return 0;
}
