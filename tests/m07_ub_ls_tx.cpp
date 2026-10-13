#include <nano/ub/tx.h>
#include <iostream>

// ---- Wire Sniffer ----
SC_MODULE(WireSniffer) {
    sc_fifo_in<Flit> in;
    std::vector<Flit> captured;
    SC_HAS_PROCESS(WireSniffer);
    WireSniffer(sc_module_name name) : sc_module(name) {
        SC_THREAD(run);
    }
    void run() { while (true) captured.push_back(in.read()); }
};

int sc_main(int, char*[]) {
    sc_fifo<Flit> f1, f2, f3, f4, f_wire;

    LsEngine    ls("ls");
    BtahBuilder btah("btah");
    NthBuilder  nth("nth");
    UbEncap     enc("enc");
    WireSniffer snk("snk");

    ls.req_in .bind(f1);  ls.req_out.bind(f2);
    btah.in   .bind(f2);  btah.out  .bind(f3);
    nth.in    .bind(f3);  nth.out   .bind(f4);
    enc.in    .bind(f4);  enc.out   .bind(f_wire);
    snk.in    .bind(f_wire);

    bool all_pass = true;

    // ---- 测试 1: Load 请求 ----
    {
        Flit req = Flit::make_valid();
        req.ta_opcode = 0x06;   // Read (Load)
        req.mem_addr  = 0x1000;
        req.mem_len   = 8;

        std::cout << "  [测试 1] Load: addr=0x1000 len=8" << std::endl;
        f1.write(req);
        sc_start(1000, SC_NS);
    }

    if (snk.captured.empty()) {
        std::cout << "  [FAIL] 无输出 flit" << std::endl;
        all_pass = false;
    } else {
        Flit& out = snk.captured[0];

        struct { const char* name; bool ok; } checks[] = {
            {"valid == true",              out.valid     == true},
            {"eth_type == 0x88B5 (UB)",    out.eth_type  == UB_ETHERTYPE},
            {"nlp == 0x01 (TP_BYPASS)",    out.nlp       == 0x01},
            {"ta_opcode == 0x06 (Read)",   out.ta_opcode == 0x06},
            {"mem_addr == 0x1000",         out.mem_addr  == 0x1000},
            {"mem_len == 8",               out.mem_len   == 8},
            {"tassn allocated (==1)",      out.tassn     == 1},
            {"src_addr == 0x000001",       out.src_addr  == 0x000001},
            {"dst_addr == 0x000002",       out.dst_addr  == 0x000002},
        };

        for (auto& c : checks) {
            std::cout << "  [" << (c.ok ? "PASS" : "FAIL") << "] " << c.name << std::endl;
            all_pass &= c.ok;
        }
    }

    // ---- 测试 2: Store 请求 ----
    {
        Flit req = Flit::make_valid();
        req.ta_opcode = 0x03;   // Write (Store)
        req.mem_addr  = 0x2000;
        req.mem_len   = 64;
        for (int i = 0; i < 16; i++) req.inline_data[i] = 0xAA + i;

        std::cout << "  [测试 2] Store: addr=0x2000 len=64" << std::endl;
        f1.write(req);
        sc_start(1000, SC_NS);
    }

    if (snk.captured.size() >= 2) {
        Flit& out = snk.captured[1];
        bool ok = (out.ta_opcode == 0x03 && out.tassn == 2 &&
                   out.mem_addr == 0x2000 && out.mem_len == 64);
        std::cout << "  [" << (ok ? "PASS" : "FAIL")
                  << "] Store: 字段正确 (tassn=" << out.tassn << ")" << std::endl;
        all_pass &= ok;
    }

    std::cout << "=== M07: " << (all_pass ? "全部通过" : "有失败") << " ===" << std::endl;
    return all_pass ? 0 : 1;
}
