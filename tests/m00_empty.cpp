#include <systemc.h>
#include <iostream>

SC_MODULE(ClockBlinker) {
    sc_in_clk clk;

    void tick() {
        std::cout << "@" << sc_time_stamp() << "  tick" << std::endl;
    }

    SC_CTOR(ClockBlinker) {
        SC_METHOD(tick);
        sensitive << clk.pos();
    }
};

int sc_main(int argc, char* argv[]) {
    // 10 ns 周期时钟 -> 100 MHz; M00 只验证 SystemC 工具链能跑。
    sc_clock clk("clk", 10, SC_NS);

    ClockBlinker cb("cb");
    cb.clk(clk);

    std::cout << "=== Nano-UB M00: SystemC 空转验证 ===" << std::endl;
    std::cout << "时钟周期: 10 ns (100 MHz)" << std::endl;
    std::cout << "跑 100 个周期..." << std::endl;

    sc_start(1000, SC_NS);  // 100 cycles × 10 ns

    std::cout << "=== 完成, 仿真时间: " << sc_time_stamp() << " ===" << std::endl;

    return 0;
}
