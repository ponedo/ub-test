#ifndef NANO_EVAL_LATENCY_MODEL_H
#define NANO_EVAL_LATENCY_MODEL_H

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

namespace nano::eval {

constexpr double kNicClockMHz = 200.0;

inline double ns_to_cycles(double ns) {
    return ns * kNicClockMHz / 1000.0;
}

struct HostPathParams {
    double pcie_mmio_ns = 150.0;
    double pcie_dma_read_wqe_ns = 500.0;
    double pcie_dma_write_cqe_ns = 250.0;
    double cqe_poll_ns = 70.0;
    double onchip_bus_ns = 30.0;
};

struct RawPathParams {
    double ub_loadstore_raw_ns = 380.0; // 76 cycles @ 200 MHz
    double ub_urma_raw_ns = 400.0;      // 80 cycles @ 200 MHz
    double roce_raw_ns = 350.0;         // 70 cycles @ 200 MHz
    double link_delay_ns = 100.0;
    uint32_t payload_bytes = 64;
};

struct LatencyBreakdown {
    std::string stack;
    double raw_nic_ns = 0.0;
    double host_ns = 0.0;
    double total_ns = 0.0;
    double cycles = 0.0;
};

inline double payload_extra_ns(uint32_t payload_bytes) {
    if (payload_bytes <= 64) return 0.0;
    const uint32_t extra_flits = (payload_bytes - 1) / 64;
    return static_cast<double>(extra_flits) * (1000.0 / kNicClockMHz);
}

inline LatencyBreakdown ub_loadstore_latency(const RawPathParams& raw,
                                             const HostPathParams& host) {
    LatencyBreakdown b;
    b.stack = "ub_loadstore";
    b.raw_nic_ns = raw.ub_loadstore_raw_ns + payload_extra_ns(raw.payload_bytes);
    b.host_ns = 2.0 * host.onchip_bus_ns;
    b.total_ns = b.raw_nic_ns + b.host_ns;
    b.cycles = ns_to_cycles(b.total_ns);
    return b;
}

inline LatencyBreakdown ub_urma_latency(const RawPathParams& raw,
                                        const HostPathParams& host) {
    LatencyBreakdown b;
    b.stack = "ub_urma";
    b.raw_nic_ns = raw.ub_urma_raw_ns + payload_extra_ns(raw.payload_bytes);
    b.host_ns = host.pcie_mmio_ns + host.pcie_dma_read_wqe_ns
              + host.pcie_dma_write_cqe_ns + host.cqe_poll_ns;
    b.total_ns = b.raw_nic_ns + b.host_ns;
    b.cycles = ns_to_cycles(b.total_ns);
    return b;
}

inline LatencyBreakdown roce_raw_latency(const RawPathParams& raw) {
    LatencyBreakdown b;
    b.stack = "roce_raw";
    b.raw_nic_ns = raw.roce_raw_ns + payload_extra_ns(raw.payload_bytes);
    b.host_ns = 0.0;
    b.total_ns = b.raw_nic_ns;
    b.cycles = ns_to_cycles(b.total_ns);
    return b;
}

inline LatencyBreakdown roce_bf_latency(const RawPathParams& raw,
                                        const HostPathParams& host) {
    LatencyBreakdown b;
    b.stack = "roce_bf";
    b.raw_nic_ns = raw.roce_raw_ns + payload_extra_ns(raw.payload_bytes);
    b.host_ns = host.pcie_mmio_ns + host.pcie_dma_write_cqe_ns
              + host.cqe_poll_ns;
    b.total_ns = b.raw_nic_ns + b.host_ns;
    b.cycles = ns_to_cycles(b.total_ns);
    return b;
}

inline LatencyBreakdown roce_dma_latency(const RawPathParams& raw,
                                         const HostPathParams& host) {
    LatencyBreakdown b;
    b.stack = "roce_dma";
    b.raw_nic_ns = raw.roce_raw_ns + payload_extra_ns(raw.payload_bytes);
    b.host_ns = host.pcie_mmio_ns + host.pcie_dma_read_wqe_ns
              + host.pcie_dma_write_cqe_ns + host.cqe_poll_ns;
    b.total_ns = b.raw_nic_ns + b.host_ns;
    b.cycles = ns_to_cycles(b.total_ns);
    return b;
}

struct StateSizing {
    uint64_t local_endpoints = 1;
    uint64_t remote_hosts = 1;
    uint64_t memory_regions = 1;
    uint64_t ub_bytes = 0;
    uint64_t roce_bytes = 0;
};

inline StateSizing state_size(uint64_t local_endpoints,
                              uint64_t remote_hosts,
                              uint64_t memory_regions) {
    constexpr uint64_t kJettyBytes = 96;
    constexpr uint64_t kTpChannelBytes = 160;
    constexpr uint64_t kUbMrBytes = 64;
    constexpr uint64_t kUbGlobalBytes = 4096;
    constexpr uint64_t kQpBytes = 224;
    constexpr uint64_t kRoceMrBytes = 64;
    constexpr uint64_t kRoceGlobalBytes = 4096;

    StateSizing s;
    s.local_endpoints = local_endpoints;
    s.remote_hosts = remote_hosts;
    s.memory_regions = memory_regions;
    s.ub_bytes = kUbGlobalBytes
               + local_endpoints * kJettyBytes
               + remote_hosts * kTpChannelBytes
               + memory_regions * kUbMrBytes;
    s.roce_bytes = kRoceGlobalBytes
                 + local_endpoints * remote_hosts * kQpBytes
                 + memory_regions * kRoceMrBytes;
    return s;
}

struct OrderingCost {
    std::string mode;
    uint32_t operations = 0;
    double mean_ns = 0.0;
    double p99_ns = 0.0;
    double throughput_mops = 0.0;
};

inline uint32_t tx_latency_cycles(const std::string& service,
                                  const std::string& exec) {
    uint32_t cycles = 25;
    if (service == "UNO") cycles -= 3;
    else if (service == "ROL") cycles += 1;
    else if (service == "ROT") cycles += 2;

    if (exec == "RO") cycles += 1;
    else if (exec == "SO") cycles += 3;
    return cycles;
}

inline uint32_t wire_flits_for_payload(uint32_t payload_bytes) {
    const uint32_t payload_flits = (payload_bytes + 63) / 64;
    return 1 + payload_flits + 1;
}

inline double throughput_wr_per_us(uint32_t n_wrs,
                                   uint32_t span_cycles) {
    if (span_cycles == 0) return 0.0;
    return static_cast<double>(n_wrs) * kNicClockMHz
         / static_cast<double>(span_cycles);
}

inline OrderingCost ordering_cost(const std::string& mode,
                                  uint32_t operations,
                                  uint32_t ro_before_so = 0) {
    constexpr double kCycleNs = 1000.0 / kNicClockMHz;
    double base_cycles = 25.0;
    double mean_cycles = base_cycles;
    double p99_cycles = base_cycles;

    if (mode == "NO") {
        mean_cycles = base_cycles;
    } else if (mode == "RO") {
        mean_cycles = base_cycles + 1.0;
    } else if (mode == "SO") {
        mean_cycles = base_cycles + 2.0 + ro_before_so;
        p99_cycles = mean_cycles + std::max<uint32_t>(1, ro_before_so / 4);
    } else if (mode == "FENCE") {
        mean_cycles = base_cycles + 2.0 + operations;
        p99_cycles = mean_cycles;
    } else if (mode == "UNO") {
        mean_cycles = base_cycles - 3.0;
    } else if (mode == "RTP") {
        mean_cycles = base_cycles + 3.0;
    }
    p99_cycles = std::max(p99_cycles, mean_cycles);

    OrderingCost c;
    c.mode = mode;
    c.operations = operations;
    c.mean_ns = mean_cycles * kCycleNs;
    c.p99_ns = p99_cycles * kCycleNs;
    c.throughput_mops = operations == 0 ? 0.0 : 1000.0 / c.mean_ns;
    return c;
}

struct LossRecoveryResult {
    double loss_rate = 0.0;
    uint32_t operations = 0;
    uint32_t window = 0;
    uint32_t expected_retransmits = 0;
    double mean_ns = 0.0;
    double goodput_mops = 0.0;
};

inline LossRecoveryResult gobackn_loss_model(double loss_rate,
                                             uint32_t operations,
                                             uint32_t window,
                                             double base_latency_ns,
                                             double rto_ns = 500.0) {
    loss_rate = std::clamp(loss_rate, 0.0, 0.99);
    const double expected_losses = static_cast<double>(operations) * loss_rate;
    const double retransmits = expected_losses * static_cast<double>(window);
    const double penalty_ns = expected_losses * rto_ns / std::max<uint32_t>(1, operations);

    LossRecoveryResult r;
    r.loss_rate = loss_rate;
    r.operations = operations;
    r.window = window;
    r.expected_retransmits = static_cast<uint32_t>(std::ceil(retransmits));
    r.mean_ns = base_latency_ns + penalty_ns;
    r.goodput_mops = 1000.0 / r.mean_ns;
    return r;
}

} // namespace nano::eval

#endif // NANO_EVAL_LATENCY_MODEL_H
