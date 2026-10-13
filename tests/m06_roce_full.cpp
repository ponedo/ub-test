#include <nano/roce/tx.h>
#include <nano/roce/rx.h>
#include <nano/eth_link.h>
#include <iostream>

// ============================================================
// M06: RoCE 完整 RC — SEND + CAS + FAA
// ============================================================

// ---- 双路 FIFO 合并器 (2 输入 → 1 输出) ----
SC_MODULE(FifoMux) {
    sc_fifo_in<Flit> in0, in1;
    sc_fifo_out<Flit> out;
    SC_HAS_PROCESS(FifoMux);
    FifoMux(sc_module_name name) : sc_module(name) {
        SC_THREAD(poll0); sensitive << in0.data_written();
        SC_THREAD(poll1); sensitive << in1.data_written();
    }
    void poll0() { while (true) { Flit f = in0.read(); out.write(f); } }
    void poll1() { while (true) { Flit f = in1.read(); out.write(f); } }
};

// ---- 响应嗅探器 ----
SC_MODULE(RespSniffer) {
    sc_fifo_in<Flit> in;
    std::vector<Flit> rx;
    SC_HAS_PROCESS(RespSniffer);
    RespSniffer(sc_module_name name) : sc_module(name) {
        SC_THREAD(run);
    }
    void run() { while (true) rx.push_back(in.read()); }
};

// ---- 测试源: SEND + CAS + FAA ----
SC_MODULE(TestSource) {
    sc_fifo_out<Flit> out;
    SC_CTOR(TestSource) { SC_THREAD(gen); }
    void gen() {
        wait(1, SC_NS);

        // 1. SEND
        Flit s = Flit::make_valid();
        s.ta_opcode = 0x00;
        s.mem_len = 8;
        for (int i = 0; i < 8; i++) s.inline_data[i] = 0xD0 + i;
        s.inline_len = 8;
        std::cout << "  [Node A] 1. SEND (8 B)" << std::endl;
        out.write(s);
        wait(1000, SC_NS);

        // 2. CAS: compare 0x42 == old → swap 0x99
        Flit c = Flit::make_valid();
        c.ta_opcode = 0x07;
        c.mem_addr  = 0x3000;
        c.mem_len   = 8;
        c.operand_a = 0x99;
        c.operand_b = 0x42;
        std::cout << "  [Node A] 2. CAS mem[0x3000]: cmp=0x42 swap=0x99" << std::endl;
        out.write(c);
        wait(1000, SC_NS);

        // 3. FAA: mem[0x3000] += 1
        Flit a = Flit::make_valid();
        a.ta_opcode = 0x0B;
        a.mem_addr  = 0x3000;
        a.mem_len   = 8;
        a.operand_a = 1;
        std::cout << "  [Node A] 3. FAA mem[0x3000]: += 1" << std::endl;
        out.write(a);
    }
};

int sc_main(int, char*[]) {
    std::cout << "=== M06: RoCE 完整 RC ===" << std::endl;

    // ========== Node A ==========
    sc_fifo<Flit> a_f1, a_f2, a_f3, a_f4, a_wire_tx;
    sc_fifo<Flit> a_wire_rx, a_decap_out;

    TestSource  a_src("a_src");
    Doorbell    a_door("a_door");
    QpTx        a_qp("a_qp", 1, 2);
    BthBuilder  a_bth("a_bth");
    RoceEncap   a_enc("a_enc");
    RoceDecap   a_decap("a_decap");
    RespSniffer a_sniff("a_sniff");

    a_src.out .bind(a_f1);
    a_door.wr_in .bind(a_f1);   a_door.wr_out.bind(a_f2);
    a_qp.in  .bind(a_f2);       a_qp.out      .bind(a_f3);
    a_bth.in .bind(a_f3);       a_bth.out     .bind(a_f4);
    a_enc.in .bind(a_f4);       a_enc.out     .bind(a_wire_tx);
    a_decap.in .bind(a_wire_rx); a_decap.out.bind(a_decap_out);
    a_sniff.in .bind(a_decap_out);

    // ========== Node B ==========
    sc_fifo<Flit> b_wire_rx, b_f1, b_f2, b_data, b_ack_route;
    sc_fifo<Flit> b_write, b_read, b_send, b_atomic, b_read_resp;
    sc_fifo<Flit> b_send_done, b_atomic_resp, b_ack_from_cpl;
    sc_fifo<Flit> b_ack_out, b_resp_mux;
    sc_fifo<Flit> b_tx_f1, b_tx_f2, b_wire_tx;

    RoceDecap      b_decap("b_decap");
    QpRx           b_qprx("b_qprx");
    BthParser      b_bthp("b_bthp");
    Dispatch       b_disp("b_disp");
    MemoryModel    b_mem("b_mem");
    RecvQueue      b_recv("b_recv");
    AtomicALU      b_atomic_alu("b_atomic_alu", b_mem.get_mem_ptr());
    CompletionGen  b_cpl("b_cpl");
    AckGen         b_ack("b_ack");
    FifoMux        b_mux("b_mux");

    // RX 连线
    b_decap.in .bind(b_wire_rx); b_decap.out .bind(b_f1);
    b_qprx.in  .bind(b_f1);      b_qprx.out  .bind(b_f2);
    b_bthp.in  .bind(b_f2);
    b_bthp.data_out.bind(b_data);
    b_bthp.ack_out .bind(b_ack_route);

    b_disp.in        .bind(b_data);
    b_disp.write_req .bind(b_write);
    b_disp.read_req  .bind(b_read);
    b_disp.send_req  .bind(b_send);
    b_disp.atomic_req.bind(b_atomic);

    // SEND: RecvQueue → CompletionGen → AckGen
    b_recv.in     .bind(b_send);
    b_recv.done_out.bind(b_send_done);
    b_cpl.in      .bind(b_send_done);
    b_cpl.cqe_out .bind(b_ack_from_cpl);
    b_ack.in      .bind(b_ack_from_cpl);
    b_ack.ack_out .bind(b_ack_out);

    // Atomic: AtomicALU → resp
    b_atomic_alu.in     .bind(b_atomic);
    b_atomic_alu.resp_out.bind(b_atomic_resp);

    // MemoryModel (未用端口绑 dummy)
    sc_fifo<Flit> b_done_dummy;
    b_mem.write_in .bind(b_write);
    b_mem.read_in  .bind(b_read);
    b_mem.write_done.bind(b_done_dummy);
    b_mem.read_resp .bind(b_read_resp);

    // 合并 ACK 和 Atomic Response → 统一 TX 管线
    b_mux.in0.bind(b_ack_out);
    b_mux.in1.bind(b_atomic_resp);
    b_mux.out.bind(b_resp_mux);

    // TX 管线 (共用)
    QpTx       b_tx_qp("b_tx_qp", 2, 1);
    BthBuilder b_tx_bth("b_tx_bth");
    RoceEncap  b_tx_enc("b_tx_enc");

    b_tx_qp.in .bind(b_resp_mux); b_tx_qp.out  .bind(b_tx_f1);
    b_tx_bth.in.bind(b_tx_f1);    b_tx_bth.out .bind(b_tx_f2);
    b_tx_enc.in.bind(b_tx_f2);    b_tx_enc.out .bind(b_wire_tx);

    // ========== 预填充 ==========
    uint64_t init_val = 0x42;
    b_mem.write_direct(0x3000, (uint8_t*)&init_val, 8);
    std::cout << "  [Node B] 预填充 mem[0x3000] = 0x42" << std::endl;

    // ========== EtherLink ==========
    EtherLink link("link", sc_time(50, SC_NS));
    link.a_to_link.bind(a_wire_tx);
    link.link_to_b.bind(b_wire_rx);
    link.b_to_link.bind(b_wire_tx);
    link.link_to_a.bind(a_wire_rx);

    // ========== 运行 ==========
    sc_start(20000, SC_NS);

    // ========== 验证 ==========
    bool all_pass = true;

    // 1. SEND 验证: RecvQueue 收到消息
    bool send_ok = (b_recv.messages.size() == 1);
    if (send_ok) {
        Flit& msg = b_recv.messages[0];
        send_ok = (msg.inline_len == 8 && msg.inline_data[0] == 0xD0);
    }
    std::cout << "  [" << (send_ok ? "PASS" : "FAIL")
              << "] SEND: RecvQueue " << (send_ok ? "收到消息" : "未收到")
              << std::endl;
    all_pass &= send_ok;

    // 4. Node A 响应验证
    // CAS 响应应返回旧值 0x42, FAA 响应应返回旧值 0x99
    bool cas_resp_ok = false, faa_resp_ok = false;
    for (auto& r : a_sniff.rx) {
        if (r.ta_opcode == 0x13) {  // Atomic Response
            if (r.operand_a == 0x42) cas_resp_ok = true;
            if (r.operand_a == 0x99) faa_resp_ok = true;
        }
    }
    // CAS 后内存应为 0x99, FAA 后为 0x9A
    // 先 CAS 再 FAA, 最终 mem = 0x9A
    uint64_t mem_final;
    std::memcpy(&mem_final, b_mem.get_mem_ptr() + 0x3000, 8);
    bool mem_final_ok = (mem_final == 0x9A);

    std::cout << "  [" << (cas_resp_ok ? "PASS" : "FAIL")
              << "] CAS: 返回旧值=" << std::hex << (cas_resp_ok ? 0x42 : 0)
              << std::dec << " (期望 0x42)" << std::endl;
    std::cout << "  [" << (faa_resp_ok ? "PASS" : "FAIL")
              << "] FAA: 返回旧值=" << std::hex << (faa_resp_ok ? 0x99 : 0)
              << std::dec << " (期望 0x99)" << std::endl;
    std::cout << "  [" << (mem_final_ok ? "PASS" : "FAIL")
              << "] 最终 mem[0x3000] = 0x" << std::hex << mem_final
              << " (期望 0x9A)" << std::dec << std::endl;
    all_pass &= cas_resp_ok && faa_resp_ok && mem_final_ok;

    std::cout << "=== M06: " << (all_pass ? "全部通过" : "有失败") << " ===" << std::endl;
    return all_pass ? 0 : 1;
}
