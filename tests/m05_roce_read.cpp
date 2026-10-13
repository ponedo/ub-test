#include <nano/roce/tx.h>
#include <nano/roce/rx.h>
#include <nano/eth_link.h>
#include <iostream>

// ============================================================
// M05: RoCE RDMA READ
//
// Node A (QP=1, initiator)         Node B (QP=2, target)
//   RdSource → TX                  Decap → RX → Memory(read)
//      ↓                               ↓
//   Decap ← ReadRespSniff ← link ←── QpTx ← read_resp
// ============================================================

// ---- ReadResponse 嗅探器 ----
SC_MODULE(ReadRespSniffer) {
    sc_fifo_in<Flit> in;
    bool got_response = false;
    Flit response;

    SC_HAS_PROCESS(ReadRespSniffer);
    ReadRespSniffer(sc_module_name name) : sc_module(name) {
        SC_THREAD(run);
    }
    void run() {
        response = in.read();
        got_response = true;
        std::cout << "  [Node A] 收到 Read Response! ta_op=0x"
                  << std::hex << (int)response.ta_opcode << std::dec
                  << " len=" << (int)response.mem_len
                  << " data[0]=" << std::hex << (int)response.inline_data[0]
                  << std::dec << std::endl;
    }
};

// ---- RDMA READ 请求源 ----
SC_MODULE(RdSource) {
    sc_fifo_out<Flit> out;
    uint64_t raddr;
    uint32_t rlen;

    SC_HAS_PROCESS(RdSource);
    RdSource(sc_module_name name, uint64_t addr=0x2000, uint32_t len=16)
        : sc_module(name), raddr(addr), rlen(len) {
        SC_THREAD(gen);
    }
    void gen() {
        Flit req = Flit::make_valid();
        req.ta_opcode = 0x06;    // READ
        req.mem_addr  = raddr;
        req.mem_len   = rlen;
        std::cout << "  [Node A] 发送 RDMA READ: mem[0x"
                  << std::hex << raddr << "+" << std::dec << rlen << "]"
                  << std::endl;
        out.write(req);
    }
};

int sc_main(int, char*[]) {
    std::cout << "=== M05: RoCE RDMA READ ===" << std::endl;

    // 先预填充 Node B 内存 (用 MemoryModel 的 handle_writes)
    // 直接构造一个 WRITE 请求打到 B 的内存
    {
        sc_fifo<Flit> wf;
        // 直接用 MemoryModel 的 write_in
        // 但这里我们直接在测试里构造
        // 更简单: 稍后直接用 b_mem 的 mem 数组
    }

    // ========== Node A ==========
    sc_fifo<Flit> a_f1, a_f2, a_f3, a_f4, a_wire_tx;
    sc_fifo<Flit> a_wire_rx, a_decap_out;

    RdSource    a_src("a_src", 0x2000, 16);
    Doorbell    a_door("a_door");
    QpTx        a_qp("a_qp", 1, 2);
    BthBuilder  a_bth("a_bth");
    RoceEncap   a_enc("a_enc");
    RoceDecap   a_decap("a_decap");
    ReadRespSniffer a_sniff("a_sniff");

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
    sc_fifo<Flit> b_done, b_cqe, b_ack_out;
    sc_fifo<Flit> b_rr_f1, b_rr_f2, b_wire_tx;

    RoceDecap      b_decap("b_decap");
    QpRx           b_qprx("b_qprx");
    BthParser      b_bthp("b_bthp");
    Dispatch       b_disp("b_disp");
    MemoryModel    b_mem("b_mem");
    CompletionGen  b_cpl("b_cpl");
    AckGen         b_ack("b_ack");
    // Read Response 回传管线 (不经过 AckGen)
    QpTx           b_rr_qp("b_rr_qp", 2, 1);
    BthBuilder     b_rr_bth("b_rr_bth");
    RoceEncap      b_rr_enc("b_rr_enc");

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

    // Read Response 回传: read_resp → QpTx → BthBuilder → Encap → wire
    b_rr_qp.in .bind(b_read_resp); b_rr_qp.out  .bind(b_rr_f1);
    b_rr_bth.in.bind(b_rr_f1);     b_rr_bth.out .bind(b_rr_f2);
    b_rr_enc.in.bind(b_rr_f2);     b_rr_enc.out .bind(b_wire_tx);

    // (保持 ACK 路径编译通过但本测试不用)
    sc_fifo<Flit> b_ack_dummy;
    b_cpl.in    .bind(b_done);   b_cpl.cqe_out .bind(b_cqe);
    b_ack.in    .bind(b_cqe);    b_ack.ack_out .bind(b_ack_dummy);

    // ========== 预填充 Node B 内存 0x2000 ==========
    {
        uint8_t pattern[16];
        for (int i = 0; i < 16; i++) pattern[i] = 0xC0 + i;
        b_mem.write_direct(0x2000, pattern, 16);
        std::cout << "  [Node B] 预填充内存 0x2000: C0 C1 ... CF" << std::endl;
    }

    // ========== EtherLink ==========
    EtherLink link("link", sc_time(100, SC_NS));
    link.a_to_link.bind(a_wire_tx);
    link.link_to_b.bind(b_wire_rx);
    link.b_to_link.bind(b_wire_tx);
    link.link_to_a.bind(a_wire_rx);

    // ========== 运行 ==========
    sc_start(10000, SC_NS);

    // ========== 验证 ==========
    bool all_pass = true;

    // 检查 Read Response
    if (!a_sniff.got_response) {
        std::cout << "  [FAIL] Node A: 未收到 Read Response" << std::endl;
        all_pass = false;
    } else {
        bool data_ok = true;
        for (int i = 0; i < 16 && i < a_sniff.response.inline_len; i++) {
            uint8_t expected = 0xC0 + i;
            if (a_sniff.response.inline_data[i] != expected) {
                data_ok = false;
                std::cout << "  [FAIL] data[" << i << "]: 期望 0x"
                          << std::hex << (int)expected << ", 实际 0x"
                          << (int)a_sniff.response.inline_data[i]
                          << std::dec << std::endl;
                break;
            }
        }
        if (data_ok) {
            std::cout << "  [PASS] Node A: Read Response 数据正确 ("
                      << (int)a_sniff.response.inline_len << " B)" << std::endl;
        }
        all_pass &= data_ok;
    }

    std::cout << "=== M05: " << (all_pass ? "全部通过" : "有失败") << " ===" << std::endl;
    return all_pass ? 0 : 1;
}
