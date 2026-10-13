#include <nano/ub/tx.h>
#include <iostream>

// ---- Wire Sniffer ----
SC_MODULE(WireSniffer) {
    sc_fifo_in<Flit> in;
    std::vector<Flit> captured;
    SC_HAS_PROCESS(WireSniffer);
    WireSniffer(sc_module_name name) : sc_module(name) { SC_THREAD(run); }
    void run() { while (true) captured.push_back(in.read()); }
};

int sc_main(int, char*[]) {
    std::cout << "=== M09: UB URMA TX 完整路径 ===" << std::endl;

    // 完整管线: Doorbell → JettySched → OrderTrk → BtahBuilder
    //   → TpgGroup → TpChTx → CongWin → RetxBuf → RtphBuilder
    //   → NthBuilder → UbEncap → Wire

    sc_fifo<Flit> f[12];
    // f[0]: Doorbell input
    // f[1]: After Doorbell
    // f[2]: After JettySched
    // f[3]: After OrderTrk
    // f[4]: After BtahBuilder
    // f[5]: After TpgGroup
    // f[6]: After TpChTx
    // f[7]: After CongWin
    // f[8]: After RetxBuf
    // f[9]: After RtphBuilder
    // f[10]: After NthBuilder
    // f[11]: After UbEncap

    UbDoorbell       door("door");
    JettyScheduler   jety("jety");
    OrderTrackerIni  otri("otri");
    BtahBuilder      btah("btah");
    TpgGroup         tpg("tpg");
    TpChannelTx      tpch("tpch");
    CongestionWindow cong("cong");
    RetransmitBuffer retx("retx");
    RtphBuilder      rtph("rtph");
    NthBuilder       nth("nth");
    UbEncap          enc("enc");
    WireSniffer      snk("snk");

    door.wr_in .bind(f[0]); door.wr_out.bind(f[1]);
    jety.in    .bind(f[1]); jety.out   .bind(f[2]);
    otri.in    .bind(f[2]); otri.out   .bind(f[3]);
    btah.in    .bind(f[3]); btah.out   .bind(f[4]);
    tpg.in     .bind(f[4]); tpg.out    .bind(f[5]);
    tpch.in    .bind(f[5]); tpch.out   .bind(f[6]);
    cong.in    .bind(f[6]); cong.out   .bind(f[7]);
    retx.in    .bind(f[7]); retx.out   .bind(f[8]);
    rtph.in    .bind(f[8]); rtph.out   .bind(f[9]);
    nth.in     .bind(f[9]); nth.out    .bind(f[10]);
    enc.in     .bind(f[10]); enc.out   .bind(f[11]);
    snk.in     .bind(f[11]);

    // JettyScheduler 和 OrderTrackerIni 的 comp_in 绑 dummy
    sc_fifo<Flit> cd1("cd1"), cd2("cd2");
    jety.comp_in.bind(cd1);
    otri.comp_in.bind(cd2);

    // RetxBuffer ACK 端口绑 dummy
    sc_fifo<Flit> ack_dummy;
    retx.ack_in.bind(ack_dummy);

    // ---- 注入一个 WR (RDMA WRITE) ----
    Flit wr = Flit::make_valid();
    wr.ta_opcode = 0x03;   // WRITE
    wr.mem_addr  = 0x1000;
    wr.mem_len   = 64;
    wr.src_addr  = 0x000001;
    wr.dst_addr  = 0x000002;
    for (int i = 0; i < 16; i++) wr.inline_data[i] = 0xDE + i;
    wr.inline_len = 16;

    std::cout << "  注入 WR: WRITE mem[0x1000+64]" << std::endl;
    f[0].write(wr);

    sc_start(2000, SC_NS);

    // ---- 验证 ----
    bool all_pass = true;

    if (snk.captured.empty()) {
        std::cout << "  [FAIL] 无输出 flit" << std::endl;
        all_pass = false;
    } else {
        Flit& out = snk.captured[0];
        std::cout << "  输出: " << out << std::endl;

        struct { const char* name; bool ok; } checks[] = {
            {"valid == true",                  out.valid     == true},
            {"eth_type == 0x88B5 (UB)",        out.eth_type  == UB_ETHERTYPE},
            {"nlp == 0x10 (RTP)",              out.nlp       == 0x10},
            {"tp_opcode == 0x01 (RTP_DATA)",   out.tp_opcode == 0x01},
            {"ta_opcode == 0x03 (WRITE)",      out.ta_opcode == 0x03},
            {"PSN allocated",                  out.psn       == 0},
            {"TASSN allocated (==1)",          out.tassn     == 1},
            {"src_addr == 0x000001",           out.src_addr  == 0x000001},
            {"dst_addr == 0x000002",           out.dst_addr  == 0x000002},
            {"mem_addr == 0x1000",             out.mem_addr  == 0x1000},
            {"mem_len == 64",                  out.mem_len   == 64},
        };

        for (auto& c : checks) {
            std::cout << "  [" << (c.ok ? "PASS" : "FAIL") << "] " << c.name << std::endl;
            all_pass &= c.ok;
        }
    }

    // ---- 测试 2: 第二个 WR 验证序列号递增 ----
    {
        Flit wr2 = Flit::make_valid();
        wr2.ta_opcode = 0x06;  // READ
        wr2.mem_addr  = 0x2000;
        wr2.mem_len   = 8;
        wr2.src_addr  = 0x000001;
        wr2.dst_addr  = 0x000002;
        f[0].write(wr2);
        sc_start(2000, SC_NS);
    }

    if (snk.captured.size() >= 2) {
        Flit& out2 = snk.captured[1];
        bool seq_ok = (out2.psn == 1 && out2.tassn == 2);
        std::cout << "  [" << (seq_ok ? "PASS" : "FAIL")
                  << " 序列号递增: PSN=" << out2.psn << " TASSN=" << out2.tassn
                  << std::endl;
        all_pass &= seq_ok;
    }

    std::cout << "=== M09: " << (all_pass ? "全部通过" : "有失败") << " ===" << std::endl;
    return all_pass ? 0 : 1;
}
