#include <nano/eth_link.h>
#include <iostream>
#include <vector>
#include <string>

// ============================================================
// M02: EtherLink 链路模型验证
//
// 一次性创建所有场景, 用 sc_signal 分阶段使能
// ============================================================

// --- 通用使能源: go 信号上升沿后发送 ---
SC_MODULE(Src) {
    sc_fifo_out<Flit> out;
    sc_in<bool>       go;
    int               count;  // 发送数量
    int               start;  // 起始 PSN

    SC_HAS_PROCESS(Src);
    Src(sc_module_name name, int c = 1, int s = 0)
        : sc_module(name), count(c), start(s) {
        SC_THREAD(run);
        sensitive << go.pos();
        dont_initialize();
    }
    void run() {
        for (int i = 0; i < count; i++) {
            Flit f = Flit::make_valid();
            f.psn = start + i;
            out.write(f);
        }
    }
};

// --- 通用接收汇 ---
SC_MODULE(Snk) {
    sc_fifo_in<Flit> in;
    std::vector<Flit> rx;

    SC_HAS_PROCESS(Snk);
    Snk(sc_module_name name) : sc_module(name) {
        SC_THREAD(collect);
    }
    void collect() {
        while (true) {
            rx.push_back(in.read());
        }
    }
};

// --- 测试结果 ---
struct Result {
    std::string name;
    bool pass;
};

// --- 测试控制器 ---
SC_MODULE(Controller) {
    sc_out<bool> go1, go2, go3;
    std::vector<Result> results;

    SC_HAS_PROCESS(Controller);
    Controller(sc_module_name name) : sc_module(name) {
        SC_THREAD(sequence);
    }

    void sequence() {
        // 先让所有 FIFO 填充
        wait(1, SC_NS);

        // ---- 测试 1: 基本延迟 ----
        go1.write(true);
        wait(2000, SC_NS);
        // 结果在外部检查
        go1.write(false);

        // ---- 测试 2: 丢包 ----
        go2.write(true);
        wait(100000, SC_NS);
        go2.write(false);

        // ---- 测试 3: 确定性 ----
        go3.write(true);
        wait(100000, SC_NS);
        go3.write(false);

        sc_stop();
    }
};

int sc_main(int, char*[]) {
    // ---- FIFO 声明 ----
    sc_fifo<Flit> fifo[6]; // 0:t1_a2b, 1:t1_b2a, 2:t2_a2b, 3:t2_b2a, 4:t3a_a2b, 5:t3a_b2a
    sc_fifo<Flit> fifo2[2]; // t3b_a2b, t3b_b2a
    sc_fifo<Flit> dummy[6]; // 每个 link 另一方向

    // ---- 信号 ----
    sc_signal<bool> go1("go1"), go2("go2"), go3("go3");

    // ---- 测试 1: 基本延迟 ----
    Src        t1_src("t1_src", 1, 42);
    Snk        t1_snk("t1_snk");
    EtherLink  t1_link("t1_link", sc_time(100, SC_NS));
    t1_src.out.bind(fifo[0]); t1_link.a_to_link.bind(fifo[0]);
    t1_link.link_to_b.bind(fifo[1]); t1_snk.in.bind(fifo[1]);
    t1_link.b_to_link.bind(dummy[0]); t1_link.link_to_a.bind(dummy[1]);
    t1_src.go.bind(go1);

    // ---- 测试 2: 丢包 ----
    Src        t2_src("t2_src", 1000, 0);
    Snk        t2_snk("t2_snk");
    EtherLink  t2_link("t2_link", sc_time(10, SC_NS), 0.0, 0.5, 123);
    t2_src.out.bind(fifo[2]); t2_link.a_to_link.bind(fifo[2]);
    t2_link.link_to_b.bind(fifo[3]); t2_snk.in.bind(fifo[3]);
    t2_link.b_to_link.bind(dummy[2]); t2_link.link_to_a.bind(dummy[3]);
    t2_src.go.bind(go2);

    // ---- 测试 3: 确定性 ----
    Src        t3_src_a("t3_src_a", 50, 0);
    Snk        t3_snk_a("t3_snk_a");
    EtherLink  t3_link_a("t3_link_a", sc_time(10, SC_NS), 0.2, 0.3, 999);
    t3_src_a.out.bind(fifo[4]); t3_link_a.a_to_link.bind(fifo[4]);
    t3_link_a.link_to_b.bind(fifo[5]); t3_snk_a.in.bind(fifo[5]);
    t3_link_a.b_to_link.bind(dummy[4]); t3_link_a.link_to_a.bind(dummy[5]);
    t3_src_a.go.bind(go3);

    Src        t3_src_b("t3_src_b", 50, 0);
    Snk        t3_snk_b("t3_snk_b");
    EtherLink  t3_link_b("t3_link_b", sc_time(10, SC_NS), 0.2, 0.3, 999);
    t3_src_b.out.bind(fifo2[0]); t3_link_b.a_to_link.bind(fifo2[0]);
    t3_link_b.link_to_b.bind(fifo2[1]); t3_snk_b.in.bind(fifo2[1]);
    sc_fifo<Flit> dummy2[2];
    t3_link_b.b_to_link.bind(dummy2[0]); t3_link_b.link_to_a.bind(dummy2[1]);
    t3_src_b.go.bind(go3);

    // ---- 控制器 ----
    Controller ctrl("ctrl");
    ctrl.go1.bind(go1);
    ctrl.go2.bind(go2);
    ctrl.go3.bind(go3);

    // ---- 运行 ----
    std::cout << "=== M02: EtherLink 链路测试 ===" << std::endl;
    sc_start();
    std::cout << "---" << std::endl;

    // ---- 检查结果 ----
    bool all_pass = true;

    // 测试 1
    bool pass1 = (t1_snk.rx.size() == 1 && t1_snk.rx[0].psn == 42);
    std::cout << "  [" << (pass1 ? "PASS" : "FAIL")
              << "] 基本延迟: flit 正确到达, psn="
              << (t1_snk.rx.empty() ? -1 : (int)t1_snk.rx[0].psn) << std::endl;
    all_pass &= pass1;

    // 测试 2
    size_t n2 = t2_snk.rx.size();
    bool pass2 = (n2 > 300 && n2 < 700);
    std::cout << "  [" << (pass2 ? "PASS" : "FAIL")
              << "] 丢包 50%: 发送 1000, 收到 " << n2 << " (预期 ~500)" << std::endl;
    all_pass &= pass2;

    // 测试 3
    bool pass3 = (t3_snk_a.rx.size() == t3_snk_b.rx.size());
    if (pass3) {
        for (size_t i = 0; i < t3_snk_a.rx.size(); i++) {
            if (t3_snk_a.rx[i].psn != t3_snk_b.rx[i].psn) { pass3 = false; break; }
        }
    }
    std::cout << "  [" << (pass3 ? "PASS" : "FAIL")
              << "] 确定性: 相同种子结果一致 ("
              << t3_snk_a.rx.size() << "/" << t3_snk_b.rx.size() << ")" << std::endl;
    all_pass &= pass3;

    std::cout << "=== M02: " << (all_pass ? "全部通过" : "有失败") << " ===" << std::endl;
    return all_pass ? 0 : 1;
}
