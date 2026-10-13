#include <nano/ub/tx.h>
#include <nano/ub/rx.h>
#include <nano/eth_link.h>
#include <iostream>

// ============================================================
// M08: UB Load/Store ping-pong — 简化版
// ============================================================

SC_MODULE(Sniffer) {
    sc_fifo_in<Flit> in;
    std::vector<Flit> rx;
    SC_HAS_PROCESS(Sniffer);
    Sniffer(sc_module_name name) : sc_module(name) { SC_THREAD(run); }
    void run() { while (true) rx.push_back(in.read()); }
};

int sc_main(int, char*[]) {
    std::cout << "=== M08: UB Load/Store ping-pong ===" << std::endl;

    // ========== Node A ==========
    sc_fifo<Flit> a_tx_f1, a_tx_f2, a_tx_f3, a_tx_f4, a_wire_tx;
    sc_fifo<Flit> a_wire_rx, a_dcout, a_ntp_bp, a_ntp_tp, a_resps;

    LsEngine    a_ls("a_ls");
    BtahBuilder a_btah("a_btah");
    NthBuilder  a_nth("a_nth");
    UbEncap     a_enc("a_enc");
    a_ls.req_in .bind(a_tx_f1);  a_ls.req_out.bind(a_tx_f2);
    a_btah.in   .bind(a_tx_f2);  a_btah.out  .bind(a_tx_f3);
    a_nth.in    .bind(a_tx_f3);  a_nth.out   .bind(a_tx_f4);
    a_enc.in    .bind(a_tx_f4);  a_enc.out   .bind(a_wire_tx);

    UbDecap    a_dc("a_dc");
    NthParser  a_np("a_np");
    BtahParser a_bp("a_bp");
    Sniffer    a_sf("a_sf");
    a_dc.in .bind(a_wire_rx); a_dc.out .bind(a_dcout);
    a_np.in .bind(a_dcout);   a_np.bypass_out.bind(a_ntp_bp);
    a_np.tp_out.bind(a_ntp_tp);
    a_bp.in.bind(a_ntp_bp);  a_bp.resp_out.bind(a_resps);
    a_sf.in.bind(a_resps);
    sc_fifo<Flit> a_r_d; a_bp.req_out.bind(a_r_d);

    // ========== Node B ==========
    sc_fifo<Flit> b_wire_rx, b_dcout, b_ntp_bp, b_ntp_tp, b_reqs, b_resps;
    sc_fifo<Flit> b_tx_f1, b_tx_f2, b_tx_f3, b_wire_tx;

    UbDecap    b_dc("b_dc");
    NthParser  b_np("b_np");
    BtahParser b_bp("b_bp");
    UbMemory   b_mem("b_mem");
    b_dc.in .bind(b_wire_rx); b_dc.out .bind(b_dcout);
    b_np.in .bind(b_dcout);   b_np.bypass_out.bind(b_ntp_bp);
    b_np.tp_out.bind(b_ntp_tp);
    b_bp.in.bind(b_ntp_bp);  b_bp.req_out.bind(b_reqs);
    b_mem.req_in.bind(b_reqs); b_mem.resp_out.bind(b_resps);
    sc_fifo<Flit> b_r_d; b_bp.resp_out.bind(b_r_d);

    // Read Response → Node B TX 回传
    BtahBuilder b_b2("b_b2");
    NthBuilder  b_n2("b_n2");
    UbEncap     b_e2("b_e2");
    b_b2.in .bind(b_resps); b_b2.out .bind(b_tx_f1);
    b_n2.in .bind(b_tx_f1); b_n2.out .bind(b_tx_f2);
    b_e2.in .bind(b_tx_f2); b_e2.out .bind(b_wire_tx);

    // ========== 预填充 ==========
    uint8_t pat[16];
    for (int i = 0; i < 16; i++) pat[i] = 0xBB + i;
    b_mem.write_direct(0x1000, pat, 16);
    std::cout << "  [Node B] 预填充 mem[0x1000]" << std::endl;

    // ========== EtherLink ==========
    EtherLink link("link", sc_time(50, SC_NS));
    link.a_to_link.bind(a_wire_tx);
    link.link_to_b.bind(b_wire_rx);
    link.b_to_link.bind(b_wire_tx);
    link.link_to_a.bind(a_wire_rx);

    // ========== 注入 Load 请求 ==========
    Flit req = Flit::make_valid();
    req.ta_opcode = 0x06;  // Load
    req.mem_addr  = 0x1000;
    req.mem_len   = 16;
    std::cout << "  [Node A] Load mem[0x1000+16]" << std::endl;
    a_tx_f1.write(req);

    // ========== 运行 ==========
    sc_start(10000, SC_NS);

    // ========== 验证 ==========
    bool load_ok = false;
    for (auto& r : a_sf.rx) {
        if (r.ta_opcode == 0x12) {
            load_ok = true;
            for (int i = 0; i < 16 && i < r.inline_len; i++) {
                if (r.inline_data[i] != (uint8_t)(0xBB + i)) load_ok = false;
            }
            std::cout << "  [INFO] 收到 Read Response, data[0]="
                      << std::hex << (int)r.inline_data[0] << std::dec << std::endl;
            break;
        }
    }
    std::cout << "  [" << (load_ok ? "PASS" : "FAIL")
              << "] Load: 读回数据正确" << std::endl;

    // ========== 注入 Store 请求 ==========
    Flit store = Flit::make_valid();
    store.ta_opcode = 0x03;  // Store
    store.mem_addr  = 0x2000;
    store.mem_len   = 16;
    for (int i = 0; i < 16; i++) store.inline_data[i] = 0xAA + i;
    store.inline_len = 16;
    std::cout << "  [Node A] Store mem[0x2000+16]" << std::endl;
    a_tx_f1.write(store);

    sc_start(5000, SC_NS);

    bool store_ok = true;
    for (int i = 0; i < 16; i++) {
        if (b_mem.get_mem_ptr()[0x2000 + i] != (uint8_t)(0xAA + i)) {
            store_ok = false; break;
        }
    }
    std::cout << "  [" << (store_ok ? "PASS" : "FAIL")
              << "] Store: 数据正确写入" << std::endl;

    bool all_pass = load_ok && store_ok;
    std::cout << "=== M08: " << (all_pass ? "全部通过" : "有失败") << " ===" << std::endl;
    return all_pass ? 0 : 1;
}
