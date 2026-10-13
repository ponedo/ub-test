#include <nano/roce/tx.h>
#include <iostream>

// ---- Wire Sniffer: 捕获输出 flit ----
SC_MODULE(WireSniffer) {
    sc_fifo_in<Flit> in;
    std::vector<Flit> captured;

    SC_HAS_PROCESS(WireSniffer);
    WireSniffer(sc_module_name name) : sc_module(name) {
        SC_THREAD(capture);
    }
    void capture() {
        while (true) {
            captured.push_back(in.read());
        }
    }
};

int sc_main(int, char*[]) {
    // FIFO 通道
    sc_fifo<Flit> f1("f_door"), f2("f_qp"), f3("f_bth"),
                  f4("f_enc"), f5("f_wire");

    // 流水线元件
    Doorbell    door("door");
    QpTx        qp("qp", 1, 2);     // SrcQP=1, DestQP=2
    BthBuilder  bth("bth");
    RoceEncap   enc("enc");
    WireSniffer snk("snk");

    // 连线
    door.wr_in.bind(f1);
    door.wr_out.bind(f2);
    qp.in.bind(f2);
    qp.out.bind(f3);
    bth.in.bind(f3);
    bth.out.bind(f4);
    enc.in.bind(f4);
    enc.out.bind(f5);
    snk.in.bind(f5);

    bool all_pass = true;

    // ---- 构造一个 RDMA WRITE WR ----
    Flit wr = Flit::make_valid();
    wr.ta_opcode = 0x03;   // WRITE
    wr.mem_addr  = 0x1000;
    wr.mem_len   = 64;
    wr.rkey      = 0x5678;

    std::cout << "=== M03: RoCE TX 最小路径 ===" << std::endl;
    std::cout << "  注入 WR: WRITE mem[0x1000+64] rkey=0x5678" << std::endl;

    f1.write(wr);  // 注入到 Doorbell

    sc_start(1000, SC_NS);

    // ---- 检查输出 ----
    if (snk.captured.empty()) {
        std::cout << "  [FAIL] 无输出 flit" << std::endl;
        all_pass = false;
    } else {
        Flit& out = snk.captured[0];
        std::cout << "  输出: " << out << std::endl;

        // 逐字段验证
        struct { const char* name; bool ok; } checks[] = {
            {"eth_type == 0x8915 (RoCE)",       out.eth_type  == ROCE_ETHERTYPE},
            {"udp_dport == 4791",               out.udp_dport == ROCE_UDP_DPORT},
            {"tp_opcode == 0x0A (WRITE)",       out.tp_opcode == 0x0A},
            {"dst_addr == 2 (DestQP)",           out.dst_addr  == 2},
            {"src_addr == 1 (SrcQP)",            out.src_addr  == 1},
            {"mem_addr == 0x1000",               out.mem_addr  == 0x1000},
            {"mem_len == 64",                    out.mem_len   == 64},
            {"PSN allocated (≥0)",               out.psn       == 0},
            {"rkey == 0x5678",                   out.rkey      == 0x5678},
            {"valid == true",                    out.valid     == true},
        };

        for (auto& c : checks) {
            std::cout << "  [" << (c.ok ? "PASS" : "FAIL") << "] " << c.name << std::endl;
            all_pass &= c.ok;
        }
    }

    std::cout << "=== M03: " << (all_pass ? "全部通过" : "有失败") << " ===" << std::endl;
    return all_pass ? 0 : 1;
}
