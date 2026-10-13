#ifndef NANO_ETH_LINK_H
#define NANO_ETH_LINK_H

#include <nano/flit.h>
#include <systemc.h>
#include <random>

// ============================================================
// EtherLink — 双向链路模型
//
// 连接两个 NIC 的导线, 支持:
//   - 可配置单向延迟 delay
//   - 可配置抖动 jitter (±比例)
//   - 可配置丢包率 loss_rate
//   - 种子确定性
// ============================================================

SC_MODULE(EtherLink) {
    // --- 端口: NIC A 侧 ---
    sc_fifo_in<Flit>  a_to_link;   // A 发出
    sc_fifo_out<Flit> link_to_a;   // A 接收

    // --- 端口: NIC B 侧 ---
    sc_fifo_in<Flit>  b_to_link;   // B 发出
    sc_fifo_out<Flit> link_to_b;   // B 接收

    // --- 配置参数 ---
    sc_time delay;          // 单向基线延迟
    double  jitter;         // 抖动 (±比例, 0.0 = 无抖动)
    double  loss_rate;      // 丢包率 (0.0 ~ 1.0)

    // --- 构造 ---
    SC_HAS_PROCESS(EtherLink);
    EtherLink(sc_module_name name,
              sc_time delay_ = sc_time(100, SC_NS),
              double jitter_ = 0.0,
              double loss_rate_ = 0.0,
              unsigned seed = 42);

private:
    // 前向线程: 从 from 读到 to, 应用延迟/抖动/丢包
    void forward_a_to_b();
    void forward_b_to_a();

    // 工具: 计算实际延迟
    sc_time apply_jitter(sc_time base);

    std::mt19937_64 rng_;
    std::uniform_real_distribution<double> dist_;
};

#endif // NANO_ETH_LINK_H
