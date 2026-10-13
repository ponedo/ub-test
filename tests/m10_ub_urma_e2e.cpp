#include <nano/ub/tx.h>
#include <nano/ub/rx.h>
#include <nano/eth_link.h>
#include <iostream>

SC_MODULE(Sniffer) {
    sc_fifo_in<Flit> in;
    std::vector<Flit> rx;
    SC_HAS_PROCESS(Sniffer);
    Sniffer(sc_module_name name) : sc_module(name) { SC_THREAD(run); }
    void run() { while (true) rx.push_back(in.read()); }
};

int sc_main(int, char*[]) {
    std::cout << "=== M10: UB URMA 端到端 ===" << std::endl;

    // ======================== Node A ========================
    sc_fifo<Flit> a_f1("a_f1"), a_f2("a_f2"), a_f3("a_f3");
    sc_fifo<Flit> a_f4("a_f4"), a_f5("a_f5"), a_f6("a_f6");
    sc_fifo<Flit> a_f7("a_f7"), a_f8("a_f8"), a_f9("a_f9");
    sc_fifo<Flit> a_f10("a_f10"), a_f11("a_f11"), a_wire_tx("a_wt");
    sc_fifo<Flit> a_wire_rx("a_wr"), a_dcout("a_dc_out");
    sc_fifo<Flit> a_ntp_tp("a_ntp_tp"), a_bp_resp("a_bp_resp");

    UbDoorbell       a_door("a_door");
    JettyScheduler   a_jety("a_jety");
    OrderTrackerIni  a_otri("a_otri");
    BtahBuilder      a_btah("a_btah");
    TpgGroup         a_tpg("a_tpg");
    TpChannelTx      a_tpch("a_tpch");
    CongestionWindow a_cong("a_cong");
    RetransmitBuffer a_retx("a_retx");
    RtphBuilder      a_rtph("a_rtph");
    NthBuilder       a_nth("a_nth");
    UbEncap          a_enc("a_enc");

    a_door.wr_in .bind(a_f1);   a_door.wr_out.bind(a_f2);
    a_jety.in    .bind(a_f2);   a_jety.out    .bind(a_f3);
    a_otri.in    .bind(a_f3);   a_otri.out    .bind(a_f4);
    a_btah.in    .bind(a_f4);   a_btah.out    .bind(a_f5);
    a_tpg.in     .bind(a_f5);   a_tpg.out     .bind(a_f6);
    a_tpch.in    .bind(a_f6);   a_tpch.out    .bind(a_f7);
    a_cong.in    .bind(a_f7);   a_cong.out    .bind(a_f8);
    a_retx.in    .bind(a_f8);   a_retx.out    .bind(a_f9);
    a_rtph.in    .bind(a_f9);   a_rtph.out    .bind(a_f10);
    a_nth.in     .bind(a_f10);  a_nth.out     .bind(a_f11);
    a_enc.in     .bind(a_f11);  a_enc.out     .bind(a_wire_tx);
    sc_fifo<Flit> a_ad("a_ad");
    a_retx.ack_in.bind(a_ad);
    sc_fifo<Flit> a_cd1("a_cd1"), a_cd2("a_cd2");
    a_jety.comp_in.bind(a_cd1);
    a_otri.comp_in.bind(a_cd2);

    // RX
    UbDecap    a_dc("a_dc");
    NthParser  a_np("a_np");
    BtahParser a_bp("a_bp");
    Sniffer    a_sf("a_sf");
    a_dc.in .bind(a_wire_rx);  a_dc.out .bind(a_dcout);
    a_np.in .bind(a_dcout);
    a_np.tp_out.bind(a_ntp_tp);
    sc_fifo<Flit> a_np_bp_d("a_np_bp_d");
    a_np.bypass_out.bind(a_np_bp_d);
    a_bp.in.bind(a_ntp_tp);    a_bp.resp_out.bind(a_bp_resp);
    a_sf.in.bind(a_bp_resp);
    sc_fifo<Flit> a_bp_req_d("a_bp_req_d");
    a_bp.req_out.bind(a_bp_req_d);

    // ======================== Node B ========================
    sc_fifo<Flit> b_wire_rx("b_wr"), b_dcout("b_dc_out");
    sc_fifo<Flit> b_ntp_tp("b_ntp_tp"), b_rp_data("b_rp_data");
    sc_fifo<Flit> b_rp_ack("b_rp_ack"), b_tch_out("b_tch_out");
    sc_fifo<Flit> b_psnr_out("b_psnr_out"), b_req("b_req");
    sc_fifo<Flit> b_ott_out("b_ott_out"), b_read("b_read");
    sc_fifo<Flit> b_mem_resp("b_mem_resp");
    sc_fifo<Flit> b_tx_f1("b_tx_f1"), b_tx_f2("b_tx_f2"), b_wire_tx("b_wt");

    UbDecap          b_dc("b_dc");
    NthParser        b_np("b_np");
    RtphParser       b_rp("b_rp");
    TpChannelRx      b_tch("b_tch");
    PsnReorder       b_psnr("b_psnr");
    BtahParser       b_bp("b_bp");
    OrderTrackerTgt  b_ott("b_ott");
    TransDispatch    b_td("b_td");
    UbMemory         b_mem("b_mem");

    b_dc.in .bind(b_wire_rx);  b_dc.out .bind(b_dcout);
    b_np.in .bind(b_dcout);    b_np.tp_out.bind(b_ntp_tp);
    sc_fifo<Flit> b_np_bp_d("b_np_bp_d");
    b_np.bypass_out.bind(b_np_bp_d);
    b_rp.in .bind(b_ntp_tp);   b_rp.data_out.bind(b_rp_data);
    b_rp.ack_out.bind(b_rp_ack);
    b_tch.in .bind(b_rp_data); b_tch.out .bind(b_tch_out);
    b_psnr.in.bind(b_tch_out); b_psnr.out.bind(b_psnr_out);
    b_bp.in .bind(b_psnr_out); b_bp.req_out.bind(b_req);
    sc_fifo<Flit> b_bp_resp_d("b_bp_resp_d");
    b_bp.resp_out.bind(b_bp_resp_d);
    b_ott.in.bind(b_req);      b_ott.out.bind(b_ott_out);
    b_td.in.bind(b_ott_out);   b_td.read_out.bind(b_read);
    sc_fifo<Flit> b_wd("b_wd"), b_ad2("b_ad2"), b_sd("b_sd");
    b_td.write_out.bind(b_wd);
    b_td.atomic_out.bind(b_ad2);
    b_td.send_out.bind(b_sd);

    b_mem.req_in.bind(b_read);
    b_mem.resp_out.bind(b_mem_resp);

    // Read Response → TX 回传
    BtahBuilder b_b2("b_b2");
    NthBuilder  b_n2("b_n2");
    UbEncap     b_e2("b_e2");
    b_b2.in .bind(b_mem_resp); b_b2.out .bind(b_tx_f1);
    b_n2.in .bind(b_tx_f1);    b_n2.out .bind(b_tx_f2);
    b_e2.in .bind(b_tx_f2);    b_e2.out .bind(b_wire_tx);

    // ======================== EtherLink ========================
    EtherLink link("link", sc_time(50, SC_NS));
    link.a_to_link.bind(a_wire_tx);
    link.link_to_b.bind(b_wire_rx);
    link.b_to_link.bind(b_wire_tx);
    link.link_to_a.bind(a_wire_rx);

    // ======================== 注入 ========================
    Flit wr = Flit::make_valid();
    wr.ta_opcode = 0x06;   // READ
    wr.mem_addr  = 0x4000;
    wr.mem_len   = 8;
    wr.src_addr  = 0x000001;
    wr.dst_addr  = 0x000002;
    std::cout << "  [Node A] URMA READ mem[0x4000+8]" << std::endl;
    a_f1.write(wr);

    sc_start(10000, SC_NS);

    // ======================== 验证 ========================
    bool all_pass = true;
    bool got = false;
    for (auto& r : a_sf.rx) {
        if (r.ta_opcode == 0x12 || r.ta_opcode == 0x11) {
            got = true;
            std::cout << "  [INFO] Node A 收到 ta_op=0x"
                      << std::hex << (int)r.ta_opcode
                      << " data[0]=" << (int)r.inline_data[0]
                      << std::dec << std::endl;
            break;
        }
    }
    std::cout << "  [" << (got ? "PASS" : "FAIL")
              << "] Node A: 收到响应" << std::endl;
    all_pass &= got;

    std::cout << "=== M10: " << (all_pass ? "全部通过" : "有失败") << " ===" << std::endl;
    return all_pass ? 0 : 1;
}
