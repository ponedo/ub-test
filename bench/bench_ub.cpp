#include <nano/ub/tx.h>
#include <nano/ub/rx.h>
#include <nano/eth_link.h>
#include <nano/eval/latency_model.h>
#include <iostream>
#include <iomanip>

SC_MODULE(Sn) { sc_fifo_in<Flit> i; sc_time t; bool h=false;
    SC_HAS_PROCESS(Sn); Sn(sc_module_name n):sc_module(n){SC_THREAD(r);}
    void r(){i.read();t=sc_time_stamp();h=true;} };

int sc_main(int,char*[]) {
    std::cout<<"=== UB Load/Store ==="<<std::endl;

    // ===== Node A =====
    sc_fifo<Flit> a_tx1("a_tx1"),a_tx2("a_tx2"),a_tx3("a_tx3"),a_tx4("a_tx4"),a_wtx("a_wtx");
    sc_fifo<Flit> a_wrx("a_wrx"),a_dco("a_dco"),a_ntp_bp("a_ntp_bp"),a_ntp_tp("a_ntp_tp");
    sc_fifo<Flit> a_bp_resp("a_bp_resp");

    LsEngine    a_ls("a_ls"); BtahBuilder a_bt("a_bt"); NthBuilder a_nb("a_nb"); UbEncap a_ue("a_ue");
    a_ls.req_in .bind(a_tx1);  a_ls.req_out.bind(a_tx2);
    a_bt.in    .bind(a_tx2);   a_bt.out    .bind(a_tx3);
    a_nb.in    .bind(a_tx3);   a_nb.out    .bind(a_tx4);
    a_ue.in    .bind(a_tx4);   a_ue.out    .bind(a_wtx);

    UbDecap    a_dc("a_dc");  NthParser a_np("a_np"); BtahParser a_bp("a_bp"); Sn a_sn("a_sn");
    a_dc.in .bind(a_wrx);  a_dc.out .bind(a_dco);
    a_np.in .bind(a_dco);  a_np.bypass_out.bind(a_ntp_bp);
    a_np.tp_out    .bind(a_ntp_tp);
    a_bp.in        .bind(a_ntp_bp);
    a_bp.resp_out  .bind(a_bp_resp);
    a_sn.i.bind(a_bp_resp);
    sc_fifo<Flit> a_req_d("a_req_d");
    a_bp.req_out   .bind(a_req_d);

    // ===== Node B =====
    sc_fifo<Flit> b_wrx("b_wrx"),b_dco("b_dco"),b_ntp_bp("b_ntp_bp"),b_ntp_tp("b_ntp_tp");
    sc_fifo<Flit> b_req("b_req"),b_resp("b_resp");
    sc_fifo<Flit> b_tx1("b_tx1"),b_tx2("b_tx2"),b_tx3("b_tx3"),b_wtx("b_wtx");

    UbDecap    b_dc("b_dc");  NthParser b_np("b_np"); BtahParser b_bp("b_bp"); UbMemory b_mem("b_mem");
    b_dc.in .bind(b_wrx);  b_dc.out .bind(b_dco);
    b_np.in .bind(b_dco);  b_np.bypass_out.bind(b_ntp_bp);
    b_np.tp_out    .bind(b_ntp_tp);
    b_bp.in        .bind(b_ntp_bp);
    b_bp.req_out   .bind(b_req);
    b_mem.req_in   .bind(b_req);
    b_mem.resp_out .bind(b_resp);
    sc_fifo<Flit> b_bp_resp("b_bp_resp");
    b_bp.resp_out  .bind(b_bp_resp);

    // Read Response → TX
    BtahBuilder b_b2("b_b2"); NthBuilder b_n2("b_n2"); UbEncap b_e2("b_e2");
    b_b2.in .bind(b_resp);  b_b2.out .bind(b_tx1);
    b_n2.in .bind(b_tx1);   b_n2.out .bind(b_tx2);
    b_e2.in .bind(b_tx2);   b_e2.out .bind(b_wtx);

    // ===== EtherLink =====
    EtherLink link("link", sc_time(100, SC_NS));
    link.a_to_link.bind(a_wtx);
    link.link_to_b.bind(b_wrx);
    link.b_to_link.bind(b_wtx);
    link.link_to_a.bind(a_wrx);

    // ===== Send READ =====
    sc_time t0=sc_time_stamp();
    Flit f=Flit::make_valid(); f.ta_opcode=6; f.mem_addr=0x1000; f.mem_len=8;
    f.src_addr=1; f.dst_addr=2;
    a_tx1.write(f);
    sc_start(10000,SC_NS);
    double ns=a_sn.h?(a_sn.t-t0).to_seconds()*1e9:99999;

    std::cout<<"  READ 8B @100ns link: "<<std::fixed<<std::setprecision(1)
             <<ns<<" ns  ("<<(uint64_t)nano::eval::ns_to_cycles(ns)<<" cyc)"<<std::endl
             <<"=== OK ==="<<std::endl;
    return 0;
}
