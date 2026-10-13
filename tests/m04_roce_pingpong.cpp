#include <nano/roce/tx.h>
#include <nano/roce/rx.h>
#include <nano/eth_link.h>
#include <iostream>

// ============================================================
// M04: RoCE ping-pong — 双节点端到端
//
// Node A (QP=1, initiator)        Node B (QP=2, target)
// ┌──────────────────┐            ┌──────────────────┐
// │ Source → TX pipe │──link(100ns)──→ Decap → RX pipe│
// │                  │            │   ↓              │
// │ Decap ← ACK sniff│←──link(100ns)── TX pipe ← AckGen│
// └──────────────────┘            └──────────────────┘
// ============================================================

// ---- ACK 嗅探器 ----
SC_MODULE(AckSniffer) {
    sc_fifo_in<Flit> in;
    bool ack_received = false;
    SC_HAS_PROCESS(AckSniffer);
    AckSniffer(sc_module_name name) : sc_module(name) {
        SC_THREAD(run);
    }
    void run() {
        Flit f = in.read();
        if (f.tp_opcode == 0x11) {
            ack_received = true;
            std::cout << "  [Node A] 收到 ACK! psn=" << f.psn << std::endl;
        }
    }
};

// ---- WR 源 ----
SC_MODULE(WrSource) {
    sc_fifo_out<Flit> out;
    SC_CTOR(WrSource) { SC_THREAD(gen); }
    void gen() {
        Flit wr = Flit::make_valid();
        wr.ta_opcode = 0x03;
        wr.mem_addr  = 0x1000;
        wr.mem_len   = 16;
        for (int i = 0; i < 16; i++) wr.inline_data[i] = 0xAA + i;
        wr.inline_len = 16;
        std::cout << "  [Node A] 发送 RDMA WRITE: mem[0x1000+16]" << std::endl;
        out.write(wr);
    }
};

int sc_main(int, char*[]) {
    std::cout << "=== M04: RoCE ping-pong ===" << std::endl;

    // ======================== Node A ========================
    sc_fifo<Flit> a_f1, a_f2, a_f3, a_f4, a_wire_tx;
    sc_fifo<Flit> a_wire_rx, a_decap_out;

    WrSource    a_src("a_src");
    Doorbell    a_door("a_door");
    QpTx        a_qp("a_qp", 1, 2);
    BthBuilder  a_bth("a_bth");
    RoceEncap   a_enc("a_enc");
    RoceDecap   a_decap("a_decap");
    AckSniffer  a_sniff("a_sniff");

    a_src.out .bind(a_f1);
    a_door.wr_in .bind(a_f1);   a_door.wr_out.bind(a_f2);
    a_qp.in  .bind(a_f2);       a_qp.out      .bind(a_f3);
    a_bth.in .bind(a_f3);       a_bth.out     .bind(a_f4);
    a_enc.in .bind(a_f4);       a_enc.out     .bind(a_wire_tx);

    a_decap.in .bind(a_wire_rx); a_decap.out.bind(a_decap_out);
    a_sniff.in .bind(a_decap_out);

    // ======================== Node B ========================
    sc_fifo<Flit> b_wire_rx, b_f1, b_f2, b_data, b_ack_route;
    sc_fifo<Flit> b_write, b_read, b_send, b_atomic, b_read_resp;
    sc_fifo<Flit> b_done, b_cqe, b_ack_out;
    sc_fifo<Flit> b_af1, b_af2, b_wire_tx;

    RoceDecap      b_decap("b_decap");
    QpRx           b_qprx("b_qprx");
    BthParser      b_bthp("b_bthp");
    Dispatch       b_disp("b_disp");
    MemoryModel    b_mem("b_mem");
    CompletionGen  b_cpl("b_cpl");
    AckGen         b_ack("b_ack");
    QpTx           b_ack_qp("b_ack_qp", 2, 1);
    BthBuilder     b_ack_bth("b_ack_bth");
    RoceEncap      b_ack_enc("b_ack_enc");

    // B RX
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

    b_mem.write_in  .bind(b_write);
    b_mem.read_in   .bind(b_read);
    b_mem.write_done.bind(b_done);
    b_mem.read_resp .bind(b_read_resp);

    b_cpl.in    .bind(b_done);   b_cpl.cqe_out .bind(b_cqe);
    b_ack.in    .bind(b_cqe);    b_ack.ack_out .bind(b_ack_out);

    // B ACK TX
    b_ack_qp.in .bind(b_ack_out); b_ack_qp.out  .bind(b_af1);
    b_ack_bth.in.bind(b_af1);     b_ack_bth.out .bind(b_af2);
    b_ack_enc.in.bind(b_af2);     b_ack_enc.out .bind(b_wire_tx);

    // ======================== EtherLink ========================
    EtherLink link("link", sc_time(100, SC_NS));
    link.a_to_link.bind(a_wire_tx);
    link.link_to_b.bind(b_wire_rx);
    link.b_to_link.bind(b_wire_tx);
    link.link_to_a.bind(a_wire_rx);

    // ======================== 运行 ========================
    sc_start(20000, SC_NS);

    // ======================== 验证 ========================
    bool all_pass = true;

    bool mem_ok = true;
    for (int i = 0; i < 16; i++) {
        if (b_mem.read_byte(0x1000 + i) != (uint8_t)(0xAA + i)) {
            mem_ok = false; break;
        }
    }
    std::cout << "  [" << (mem_ok ? "PASS" : "FAIL")
              << "] Node B 内存: 数据正确写入" << std::endl;
    all_pass &= mem_ok;

    std::cout << "  [" << (a_sniff.ack_received ? "PASS" : "FAIL")
              << "] Node A ACK: "
              << (a_sniff.ack_received ? "已收到" : "未收到") << std::endl;
    all_pass &= a_sniff.ack_received;

    std::cout << "=== M04: " << (all_pass ? "全部通过" : "有失败") << " ===" << std::endl;
    return all_pass ? 0 : 1;
}
